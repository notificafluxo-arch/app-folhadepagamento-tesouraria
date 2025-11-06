import streamlit as st
import pandas as pd
import io
import unidecode

st.set_page_config(page_title="📊 App Folha de Pagamento", layout="wide")
st.title("📊 App Folha de Pagamento")

# Upload do arquivo
uploaded_file = st.file_uploader("Carregue a planilha da folha (.xlsx)", type=["xlsx"])

if uploaded_file:
    # Lê a planilha
    base = pd.read_excel(uploaded_file, header=0)

    # === VINCULAR POR POSIÇÃO DAS COLUNAS ===
    # (Ignora colunas extras)
    base = base.iloc[:, :8]  # Garante até a coluna H (índice 7)
    base.columns = [
        "ORGANOGRAMA",              # Coluna A (0)
        "DESCRIÇÃO DO ORGANOGRAMA", # Coluna B (1)
        "EVENTO",                   # Coluna C (2)
        "DESCRIÇÃO DO EVENTO",      # Coluna D (3)
        "P/D/PATRONAL",             # Coluna E (4)
        "VÍNCULO",                  # Coluna F (5)
        "DESCRIÇÃO DO VÍNCULO",     # Coluna G (6)
        "VALOR DO EVENTO"           # Coluna H (7)
    ]

    # === Criar coluna "FONTE DE RECURSO" ===
    base["FONTE DE RECURSO"] = base["ORGANOGRAMA"].astype(str).str[-8:]

    # === Coluna IR ===
    base["IR"] = base["DESCRIÇÃO DO EVENTO"].apply(
        lambda x: "IR" if str(x).strip().upper() in ["I.R.R.F.", "I.R.R.F. 13º SALÁRIO"] else ""
    )

    # =====================
    # Aba 1 - Folha de Pagamento
    # =====================
    folha_pagamento = (
        base.groupby("FONTE DE RECURSO")
        .apply(lambda g: pd.Series({
            "Proventos": g.loc[g["P/D/PATRONAL"] == "P", "VALOR DO EVENTO"].sum(),
            "Descontos": g.loc[g["P/D/PATRONAL"] == "D", "VALOR DO EVENTO"].sum(),
            "Auxilio_Alimentacao": g.loc[
                g["DESCRIÇÃO DO EVENTO"].str.contains("AUXILIO ALIMENTACAO", case=False, na=False),
                "VALOR DO EVENTO"
            ].sum(),
            "IR": g.loc[
                g["DESCRIÇÃO DO EVENTO"].isin(["I.R.R.F.", "I.R.R.F. 13º SALÁRIO"]),
                "VALOR DO EVENTO"
            ].sum()
        }))
        .reset_index()
    )

    folha_pagamento["Liquido"] = (
        folha_pagamento["Proventos"] - folha_pagamento["Descontos"] - folha_pagamento["Auxilio_Alimentacao"]
    )
    folha_pagamento["Total Liquido com Vale"] = (
        folha_pagamento["Proventos"] - folha_pagamento["Descontos"]
    )

    # =====================
    # Aba 2 - Retenções
    # =====================
    retencoes = (
        base[base["P/D/PATRONAL"] == "D"]
        .pivot_table(
            index="DESCRIÇÃO DO EVENTO",
            columns="FONTE DE RECURSO",
            values="VALOR DO EVENTO",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    # =====================
    # Aba 3 - Previdência
    # =====================
    previdencia_filtros = [unidecode.unidecode(f).upper().strip() for f in [
        "CONTRIBUICAO SIMPAS",
        "CONTRIBUICAO SIMPAS 13º SALARIO",
        "PREVIDENCIA MUNICIPAL - PATRONAL FUNDO"
    ]]

    previdencia = (
        base[base["DESCRIÇÃO DO EVENTO"].apply(
            lambda x: any(f in unidecode.unidecode(str(x)).upper().strip() for f in previdencia_filtros)
        )]
        .pivot_table(
            index="DESCRIÇÃO DO EVENTO",
            columns="FONTE DE RECURSO",
            values="VALOR DO EVENTO",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    # === Exibição em abas ===
    aba1, aba2, aba3 = st.tabs([
        "📑 Folha de Pagamento",
        "💰 Retenções",
        "🏦 Previdência"
    ])

    with aba1:
        st.dataframe(folha_pagamento, use_container_width=True)
    with aba2:
        st.dataframe(retencoes, use_container_width=True)
    with aba3:
        st.dataframe(previdencia, use_container_width=True)

    # === Download do Excel ===
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        folha_pagamento.to_excel(writer, sheet_name="Folha de Pagamento", index=False)
        retencoes.to_excel(writer, sheet_name="Retenções", index=False)
        previdencia.to_excel(writer, sheet_name="Previdência", index=False)

    st.download_button(
        label="📥 Baixar resultado em Excel",
        data=output.getvalue(),
        file_name="resultado_folha_rhstyle.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

