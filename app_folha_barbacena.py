import streamlit as st
import pandas as pd
import io
import unidecode

st.set_page_config(page_title="📊 App Folha de Pagamento - RH", layout="wide")

st.title("📊 App Folha de Pagamento - RH")

# Upload do arquivo
uploaded_file = st.file_uploader("Carregue a planilha da folha (.xlsx)", type=["xlsx"])

if uploaded_file:
    # Lê a planilha
    base = pd.read_excel(uploaded_file)

    # Normaliza nomes das colunas
    base.columns = base.columns.str.strip().str.upper()

    # Mapeamento dos cabeçalhos para garantir flexibilidade
    col_map = {
        "ORGANOGRAMA": "ORGANOGRAMA",
        "DESCRIÇÃO DO ORGANOGRAMA": "DESCRIÇÃO DO ORGANOGRAMA",
        "EVENTO": "EVENTO",
        "DESCRIÇÃO DO EVENTO": "DESCRIÇÃO DO EVENTO",
        "P/D/PATRONAL": "P/D/PATRONAL",
        "VÍNCULO": "VÍNCULO",
        "DESCRIÇÃO DO VÍNCULO": "DESCRIÇÃO DO VÍNCULO",
        "VALOR DO EVENTO": "VALOR DO EVENTO"
    }

    for key, col in col_map.items():
        if col not in base.columns:
            st.error(f"❌ Coluna obrigatória não encontrada: {col}")
            st.stop()

    # Criar coluna Fonte de Recurso
    base["FONTE DE RECURSO"] = base["ORGANOGRAMA"].astype(str).str[-8:]

    # =====================
    # Aba 1 - Folha de Pagamento (Proventos, Descontos, Auxílio)
    # =====================
    folha_pagamento = (
        base.groupby("FONTE DE RECURSO")
        .apply(lambda g: pd.Series({
            "Proventos": g.loc[g["P/D/PATRONAL"] == "P", "VALOR DO EVENTO"].sum(),
            "Descontos": g.loc[g["P/D/PATRONAL"] == "D", "VALOR DO EVENTO"].sum(),
            "Auxilio_Alimentacao": g.loc[g["DESCRIÇÃO DO EVENTO"].str.contains("AUXILIO ALIMENTACAO", case=False, na=False), "VALOR DO EVENTO"].sum()
        }))
        .reset_index()
    )

    folha_pagamento["Liquido"] = folha_pagamento["Proventos"] - folha_pagamento["Descontos"] - folha_pagamento["Auxilio_Alimentacao"]
    folha_pagamento["Total Liquido com Vale"] = folha_pagamento["Proventos"] - folha_pagamento["Descontos"]

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

    # Filtrar sem acento e sem diferença entre maiúsculas/minúsculas
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

    # Exibição em abas
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

    # Botão de download
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

