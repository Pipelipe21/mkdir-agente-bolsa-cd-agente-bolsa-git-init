"""Indicadores técnicos en pandas puro.

Todas las funciones reciben Series y devuelven Series/DataFrame alineados con el índice de entrada.
Los primeros valores quedan en NaN mientras no haya historia suficiente.
"""

import pandas as pd


def sma(close: pd.Series, length: int) -> pd.Series:
    return close.rolling(length, min_periods=length).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """RSI de Wilder (medias con alpha = 1/length). Rango 0–100."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    result = 100 - 100 / (1 + avg_gain / avg_loss)
    # Serie plana (sin ganancias ni pérdidas): 0/0 → RSI neutro.
    flat = (avg_gain == 0) & (avg_loss == 0)
    return result.mask(flat, 50.0)


def bollinger(close: pd.Series, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    """Bandas de Bollinger con desviación estándar poblacional (ddof=0)."""
    mid = sma(close, length)
    dev = close.rolling(length, min_periods=length).std(ddof=0)
    return pd.DataFrame(
        {"bb_lower": mid - std * dev, "bb_mid": mid, "bb_upper": mid + std * dev},
        index=close.index,
    )


def relative_volume(volume: pd.Series, length: int = 20) -> pd.Series:
    """Volumen de la vela / promedio de las `length` velas anteriores (sin incluir la actual)."""
    baseline = volume.shift(1).rolling(length, min_periods=length).mean()
    return volume / baseline


def add_indicators(candles: pd.DataFrame) -> pd.DataFrame:
    """Agrega las columnas de indicadores de la fase 1 a un DataFrame OHLCV."""
    out = candles.copy()
    close = out["close"]
    out["rsi_14"] = rsi(close, 14)
    out["sma_50"] = sma(close, 50)
    out["sma_200"] = sma(close, 200)
    out = out.join(bollinger(close, 20, 2.0))
    out["rel_volume_20"] = relative_volume(out["volume"], 20)
    return out
