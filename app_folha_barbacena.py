import streamlit as st
import pandas as pd
import io
import unidecode
import numpy as np

st.set_page_config(page_title="📊 App Folha de Pagamento", layout="wide")
st.title("📊 App Folha de Pagamento")

# Upload do arquivo
uploaded_file = st.file_uploader("Carregue a planilha da folha (.xlsx)", type=["xlsx"])

if uploaded_file:
    # Lê a primeira aba da planilha
    base = pd.read_excel(uploaded_file, header=0)

    # Usa apenas as 8 primeiras colunas (A até H) e ignora colunas extras
    if base.shape[1] < 8:
        st.error("❌ A planilha precisa ter pelo menos 8 colunas (A até H).")
        st.stop()
    base = base.iloc[:, :8].copy()

    # Padroniza e cria colunas internas com nomes esperados pelo restante do código
    # Mapeamento por posição (0..7) -> nomes usados no seu código original
    base['FONTE FINAL'] = base.iloc[:, 0]
    base['FONTE'] = base.iloc[:, 1]
    base['EVENTO_COD'] = base.iloc[:, 2]
    base['NOME EVENTO'] = base.iloc[:, 3]
    base['TIPO P/D'] = base.iloc[:, 4]
    base['NOME VINCULO'] = base.iloc[:, 5]
    base['ORGANOGRAMA'] = base.iloc[:, 6]
    base['VALOR ORIGINAL'] = base.iloc[:, 7]

    # Normaliza strings (remove acento e deixa em maiúsculas) somente nas colunas de texto
    str_cols = ['FONTE FINAL','FONTE','EVENTO_COD','NOME EVENTO','TIPO P/D','NOME VINCULO','ORGANOGRAMA']
    for c in str_cols:
        # Se coluna existir e for object, normaliza; caso contrário, converte para string e normaliza
        base[c] = base[c].astype(str).apply(lambda x: unidecode.unidecode(x).strip().upper())

    # Garante que VALOR ORIGINAL seja numérico (padrão 0 quando inválido)
    base['VALOR ORIGINAL'] = pd.to_numeric(base['VALOR ORIGINAL'], errors='coerce').fillna(0.0)

    # =====================
    # Cálculo do IR por FONTE FINAL
    # Critério: NOME EVENTO contendo "I.R.R.F." ou "I.R.R.F. 13º SALÁRIO" (comparação sem acento)
    # =====================
    def eh_ir(text):
        t = unidecode.unidecode(str(text)).upper()
        return ("I.R.R.F." in t) or ("IRRF" in t) or ("I.R.R.F" in t) or ("I.R.R.F. 13" in t) or ("13 SALARIO" in t and "IRRF" in t)

    # coluna booleana para identificar IR nos eventos
    base['__IS_IR'] = base['NOME EVENTO'].apply(lambda x: eh_ir(x))

    # =====================
    # === Folha de Pagamento ===
    # Queremos que a planilha 'Folha de Pagamento' final tenha a coluna IR sempre em G.
    # Montamos o dataframe com as colunas desejadas na ordem final:
    # [FONTE FINAL, Proventos, Descontos, Auxilio_Alimentacao, Liquido, Total Liquido com Vale, IR]
    # (Assim colocando IR como sétima coluna - que corresponde à coluna G no Excel)
    # =====================

    # Agrega proventos, descontos, auxílio e IR por FONTE FINAL
    folha_pagamento = (
        base.groupby("FONTE FINAL")
        .apply(lambda g: pd.Series({
            "Proventos": g.loc[g["TIPO P/D"] == "P", "VALOR ORIGINAL"].sum(),
            "Descontos": g.loc[g["TIPO P/D"] == "D", "VALOR ORIGINAL"].sum(),
            "Auxilio_Alimentacao": g.loc[g["NOME EVENTO"].str.contains("AUXILIO ALIMENTACAO", case=False, na=False), "VALOR ORIGINAL"].sum(),
            # IR: soma dos valores onde __IS_IR == True
            "IR": g.loc[g["__IS_IR"], "VALOR ORIGINAL"].sum()
        }))
        .reset_index()
    )

    # Calcula Líquido e Total Líquido com Vale
    folha_pagamento["Liquido"] = (
        folha_pagamento["Proventos"]
        - folha_pagamento["Descontos"]
        - folha_pagamento["Auxilio_Alimentacao"]
    )

    folha_pagamento["Total Liquido com Vale"] = (
        folha_pagamento["Proventos"] - folha_pagamento["Descontos"]
    )

    # Reordena colunas para garantir que IR fique exatamente na 7ª posição (coluna G)
    # Ordem final: FONTE FINAL, Proventos, Descontos, Auxilio_Alimentacao, Liquido, Total Liquido com Vale, IR
    # (atenção: IR foi calculado; aqui movemos ele para a última coluna e, em seguida,
    #  rearranjamos para garantir posição G — caso queira outra posição, ajuste a lista)
    folha_pagamento = folha_pagamento[[
        "FONTE FINAL",
        "Proventos",
        "Descontos",
        "Auxilio_Alimentacao",
        "Liquido",
        "Total Liquido com Vale",
        "IR"
    ]]

    # =====================
    # === Retenções ===
    # Usa NOME EVENTO index e FONTE FINAL colunas, valores VALOR ORIGINAL
    # =====================
    retencoes = (
        base[base["TIPO P/D"] == "D"]
        .pivot_table(
            index="NOME EVENTO",
            columns="FONTE FINAL",
            values="VALOR ORIGINAL",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    # =====================
    # === Previdência ===
    # Filtro por nomes aproximados (sem acento)
    # =====================
    previdencia_filtros_raw = [
        "CONTRIBUICAO SIMPAS",
        "CONTRIBUICAO SIMPAS 13º SALARIO",
        "PREVIDENCIA MUNICIPAL - PATRONAL FUNDO"
    ]
    previdencia_filtros = [unidecode.unidecode(f).upper() for f in previdencia_filtros_raw]

    previdencia = (
        base[base["NOME EVENTO"].apply(lambda x: any(f in unidecode.unidecode(str(x)).upper() for f in previdencia_filtros))]
        .pivot_table(
            index="NOME EVENTO",
            columns="FONTE FINAL",
            values="VALOR ORIGINAL",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    # =====================
    # === Conferência RH ===
    # Pivot por ["NOME VINCULO", "NOME EVENTO", "ORGANOGRAMA"], columns = FONTE, values = VALOR ORIGINAL
    # =====================
    conferencia_rh = (
        base.pivot_table(
            index=["NOME VINCULO", "NOME EVENTO", "ORGANOGRAMA"],
            columns="FONTE",
            values="VALOR ORIGINAL",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    # Exibição em abas (mantendo as 4 abas originais)
    aba1, aba2, aba3, aba4 = st.tabs([
        "📑 Folha de Pagamento",
        "💰 Retenções",
        "🏦 Previdência",
        "🧾 Conferência RH"
    ])

    with aba1:
        st.dataframe(folha_pagamento, use_container_width=True)

    with aba2:
        st.dataframe(retencoes, use_container_width=True)

    with aba3:
        st.dataframe(previdencia, use_container_width=True)

    with aba4:
        st.dataframe(conferencia_rh, use_container_width=True)

    # Botão de download: cria um Excel com as 4 abas
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        folha_pagamento.to_excel(writer, sheet_name="Folha de Pagamento", index=False)
        retencoes.to_excel(writer, sheet_name="Retenções", index=False)
        previdencia.to_excel(writer, sheet_name="Previdência", index=False)
        conferencia_rh.to_excel(writer, sheet_name="Conferência RH", index=False)

        # Ajuste: define largura mínima das colunas na planilha de saída (opcional)
        workbook = writer.book
        for sheet_name in ["Folha de Pagamento", "Retenções", "Previdência", "Conferência RH"]:
            try:
                worksheet = writer.sheets[sheet_name]
                worksheet.set_column(0, 10, 20)  # col 0..10 largura 20
            except Exception:
                pass

    st.download_button(
        label="📥 Baixar resultado em Excel",
        data=output.getvalue(),
        file_name="resultado_folha.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Opcional: mostrar mapeamento que foi aplicado (útil para conferência)
    with st.expander("🧩 Mapeamento por posição (colunas usadas 0..7)"):
        st.write({
            0: "FONTE FINAL",
            1: "FONTE",
            2: "EVENTO_COD",
            3: "NOME EVENTO",
            4: "TIPO P/D",
            5: "NOME VINCULO",
            6: "ORGANOGRAMA",
            7: "VALOR ORIGINAL"
        })

