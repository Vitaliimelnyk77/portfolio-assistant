import pandas as pd
import zipfile
import io


def parse_xtb_file(uploaded_file):
    try:
        name = uploaded_file.name
        raw = uploaded_file.read()

        if name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                results = []
                total_trades = 0
                for fname in z.namelist():
                    if fname.endswith('.xlsx') or fname.endswith('.xls'):
                        with z.open(fname) as f:
                            text, count = _parse(io.BytesIO(f.read()), fname)
                            if count > 0:
                                results.append(text)
                                total_trades += count
                if results:
                    return "\n\n".join(results), total_trades
                return "В ZIP файле нет сделок", 0

        return _parse(io.BytesIO(raw), name)

    except Exception as e:
        return f"Ошибка: {e}", 0


def _parse(fileobj, fname):
    try:
        df_raw = pd.read_excel(fileobj, engine="openpyxl", header=None)

        try:
            balance = df_raw.iloc[8, 5]
            equity = df_raw.iloc[8, 8]
            margin = df_raw.iloc[8, 11]
            free_margin = df_raw.iloc[8, 14]
        except Exception:
            balance = equity = margin = free_margin = "nd"

        header_row = None
        for i in range(len(df_raw)):
            row_vals = [str(v) for v in df_raw.iloc[i].values]
            if 'Position' in row_vals:
                header_row = i
                break

        if header_row is None:
            return f"No data in {fname}", 0

        fileobj.seek(0)
        df = pd.read_excel(fileobj, engine="openpyxl", header=header_row)
        df = df.dropna(axis=1, how='all')
        df = df[df.iloc[:, 0].astype(str).str.strip() != 'Total']
        df = df[df.iloc[:, 0].astype(str).str.strip() != 'nan']
        df = df.dropna(subset=[df.columns[0]])

        if len(df) == 0:
            return f"No trades in {fname}", 0

        account_name = fname.split('_')[1] if '_' in fname else fname

        lines = [f"=== ACCOUNT: {account_name} ==="]
        lines.append(f"Balance: {balance} PLN | Equity: {equity} PLN")
        lines.append(f"Margin: {margin} PLN | Free margin: {free_margin} PLN")
        lines.append("")

        pl_col = None
        for col in df.columns:
            if 'Gross' in str(col) or 'P/L' in str(col):
                pl_col = col
                break

        if pl_col:
            df[pl_col] = pd.to_numeric(df[pl_col], errors='coerce')
            total_pl = df[pl_col].sum()
            winners = df[df[pl_col] > 0]
            losers = df[df[pl_col] < 0]

            lines.append(f"Total trades: {len(df)}")
            lines.append(f"Winners: {len(winners)} | Losers: {len(losers)}")
            lines.append(f"Total P&L: {total_pl:.2f} PLN")
            if len(df) > 0:
                lines.append(f"Win rate: {len(winners)/len(df)*100:.1f}%")
            lines.append("")

            sym_col = 'Symbol' if 'Symbol' in df.columns else df.columns[1]
            by_sym = df.groupby(sym_col)[pl_col].agg(['count', 'sum']).sort_values('sum', ascending=False)
            lines.append("--- By instrument ---")
            for sym, row in by_sym.iterrows():
                pl = row['sum']
                sign = "+" if pl > 0 else ""
                lines.append(f"{sym}: {int(row['count'])} trades, P&L: {sign}{pl:.2f} PLN")
            lines.append("")

            lines.append("--- All trades ---")
            type_col = 'Type' if 'Type' in df.columns else df.columns[2]
            vol_col = 'Volume' if 'Volume' in df.columns else df.columns[3]
            open_col = 'Open price' if 'Open price' in df.columns else df.columns[5]
            close_col = 'Close price' if 'Close price' in df.columns else df.columns[7]

            for _, row in df.iterrows():
                pl = row[pl_col]
                sign = "+" if pl > 0 else ""
                lines.append(
                    f"{row[sym_col]} {row[type_col]} vol:{row[vol_col]} "
                    f"price:{row[open_col]}->{row[close_col]} "
                    f"P&L:{sign}{pl:.2f} PLN"
                )

        lines.append("=== END ===")
        return "\n".join(lines), len(df)

    except Exception as e:
        return f"Parse error {fname}: {e}", 0
