"""Contexto con Claude para las alertas.

El LLM solo resume y explica: nunca decide operaciones. Si falla, la alerta sale igual sin resumen.
"""

import logging
from collections.abc import Callable

import anthropic

from core.data.news import Headline
from core.models import Asset, Signal

log = logging.getLogger(__name__)

MODEL = "claude-opus-5"

SYSTEM_PROMPT = """\
Das contexto de noticias a un inversionista individual que recibe alertas técnicas de acciones \
y cripto. Las alertas las generan reglas fijas (RSI, medias móviles, Bollinger, volumen); tú no \
las generas ni las evalúas.

Con los titulares recientes del activo, escribe en español un máximo de 3 viñetas cortas \
(empieza cada una con "• ") sobre qué está pasando con el activo y si alguna noticia podría \
explicar el movimiento que disparó la alerta. Usa solo la información de los titulares, sin \
inventar datos. Si los titulares no son relevantes, dilo en una línea.

No recomiendes comprar, vender ni mantener, y no des precios objetivo ni predicciones: la \
decisión es del usuario. Responde en texto plano, sin Markdown."""


def build_prompt(signal: Signal, headlines: list[Headline]) -> str:
    lines = [
        f"Activo: {signal.asset.symbol} ({signal.asset.type})",
        f"Alerta: {signal.direction} por '{signal.strategy}' — {signal.reason}",
        "",
        "Titulares recientes:",
    ]
    for h in headlines:
        date = f"{h.published:%Y-%m-%d}" if h.published else "s/f"
        lines.append(f"- [{date}] {h.title} ({h.publisher or 'fuente desconocida'})")
        if h.summary:
            lines.append(f"  {h.summary}")
    return "\n".join(lines)


class NewsSummarizer:
    """Resume titulares por activo. Un resumen por activo por corrida (caché en memoria)."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        fetch: Callable[[Asset], list[Headline]],
        model: str = MODEL,
    ):
        self.client = client
        self.fetch = fetch
        self.model = model
        self._cache: dict[str, str | None] = {}

    def __call__(self, signal: Signal) -> str | None:
        key = signal.asset.symbol
        if key not in self._cache:
            self._cache[key] = self._summarize(signal)
        return self._cache[key]

    def _summarize(self, signal: Signal) -> str | None:
        try:
            headlines = self.fetch(signal.asset)
        except Exception:  # noqa: BLE001 — sin noticias no se bloquea la alerta
            log.warning("No se pudieron obtener noticias de %s", signal.asset.symbol, exc_info=True)
            return None
        if not headlines:
            return None

        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_prompt(signal, headlines)}],
                output_config={"effort": "low"},
                # Si el modelo rechaza la solicitud, la API la reintenta con un modelo de respaldo.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError:
            log.error("ANTHROPIC_API_KEY inválida; se omite el resumen")
            return None
        except anthropic.RateLimitError:
            log.warning("Límite de uso de Claude alcanzado; se omite el resumen")
            return None
        except anthropic.APIStatusError as exc:
            log.warning("Error %s de la API de Claude: %s", exc.status_code, exc.message)
            return None
        except anthropic.APIConnectionError:
            log.warning("Sin conexión con la API de Claude; se omite el resumen")
            return None

        if response.stop_reason == "refusal":
            log.warning("Claude rechazó resumir %s", signal.asset.symbol)
            return None
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return text or None
