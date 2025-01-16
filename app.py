import pandas as pd
import numpy as np
import streamlit as st

# Função para carregar os dados
def load_data(uploaded_file):
    try:
        # Tentar carregar o arquivo sem cabeçalho
        if uploaded_file.name.endswith('.csv'):
            data = pd.read_csv(uploaded_file, header=None)
        elif uploaded_file.name.endswith('.xlsx'):
            data = pd.read_excel(uploaded_file, header=None)
        elif uploaded_file.name.endswith('.dat'):
            data = pd.read_csv(uploaded_file, sep=r',', header=None)
        else:
            st.error("Formato de arquivo não suportado. Use .dat, .csv ou .xlsx.")
            return None

        # Remover a primeira coluna
        data = data.iloc[:, 1:]

        # Definir o cabeçalho fixo
        fixed_columns = [
            "ANO", "DIAJ", "HORA", "TEMP", "BATERIA", "SENSOR1", "SENSOR2", "SENSOR3", "SENSOR4", "SENSOR5",
            "SENSOR6", "SENSOR7", "SENSOR8", "SENSOR9", "SENSOR10"
        ]

        if len(data.columns) > len(fixed_columns):
            st.warning("O número de colunas no arquivo é maior do que o esperado. Colunas extras serão descartadas.")
            data = data.iloc[:, :len(fixed_columns)]
        elif len(data.columns) < len(fixed_columns):
            st.error(f"O número de colunas no arquivo é menor do que o esperado ({len(data.columns)} em vez de {len(fixed_columns)}). Verifique o arquivo.")
            return None

        # Atualizar os nomes das colunas
        data.columns = fixed_columns

        # Garantir que as colunas essenciais existem
        if not all(col in data.columns for col in ["ANO", "DIAJ", "HORA"]):
            st.error("As colunas obrigatórias 'ANO', 'DIAJ' e 'HORA' não foram encontradas após o processamento.")
            return None

    except Exception as e:
        st.error(f"Erro ao carregar o arquivo: {e}")
        return None

    return data

# Função para calcular o fluxo de seiva
def calcular_fluxo(data):
    required_columns = ["HORA", "DIAJ"]
    for col in required_columns:
        if col not in data.columns:
            raise KeyError(f"A coluna necessária '{col}' não está presente nos dados carregados. Colunas detectadas: {', '.join(data.columns)}")

    sa_values = [
        0.012393432, 0.012685685, 0.012685685, 0.011656805, 0.008411675,
        0.011360502, 0.005917559, 0.00330177, 0.005451517, 0.009728558
    ]

    # Validar número de sensores
    sensor_columns = [col for col in data.columns if col.startswith('SENSOR')]
    if len(sensor_columns) > len(sa_values):
        raise IndexError(f"O número de sensores no arquivo ({len(sensor_columns)}) excede o número esperado ({len(sa_values)}). Verifique os dados.")

    # Tratamento de dados
    data["HORA"] = data["HORA"].astype(int)

    # Filtrar dados por horário entre 06:00 e 18:00 (360 a 1080 minutos)
    data_filtered = data[(data["HORA"] >= 360) & (data["HORA"] <= 1080)]
    data_filtered.iloc[:, 4:] = data_filtered.iloc[:, 4:].applymap(lambda x: x if isinstance(x, (int, float)) and x >= 0 else np.nan)

    # Aplicar a fórmula de Delgado-Rojas
    Q_values = pd.DataFrame()
    for i, sensor in enumerate(sensor_columns):
        sa = sa_values[i]  # Área de alburno correspondente
        max_value = data_filtered[sensor].max()
        if max_value > 0:
            Q_values[sensor] = 478.017e-6 * ((data_filtered[sensor] / max_value) ** 1.231) * sa * 1000
        else:
            Q_values[sensor] = np.nan  # Evitar divisão por zero

    # Somatório diário por sensor
    Q_daily = Q_values.groupby(data_filtered["DIAJ"]).sum()

    # Somatório mensal e cálculo da média por clone
    clones = {
        "CLONE1": ["SENSOR1", "SENSOR2", "SENSOR3", "SENSOR4", "SENSOR5"],
        "CLONE2": ["SENSOR6", "SENSOR7", "SENSOR8", "SENSOR9", "SENSOR10"]
    }

    clone_monthly = {}
    for clone, sensors in clones.items():
        monthly_sum = Q_daily[sensors].sum(axis=1).sum()
        monthly_mean = (monthly_sum / len(sensors)) * 0.44
        clone_monthly[clone] = monthly_mean

    Q_monthly = Q_daily.sum(axis=0).to_frame(name="VALOR_MENSAL")
    df_clone = pd.DataFrame(list(clone_monthly.items()), columns=["CLONE", "MEDIA_MENSAL"])

    return Q_daily, Q_monthly, df_clone

# Configurar a interface do Streamlit
st.subheader("Análise de Fluxo de Seiva - Método Delgado-Rojas", divider=True)

# Upload do arquivo
data_file = st.file_uploader("Faça upload do arquivo de dados", type=["dat", "csv", "xlsx"])

if data_file is not None:
    # Carregar os dados
    data = load_data(data_file)

    if data is not None:
        st.write("Dados carregados com sucesso! Exibindo os dados brutos para validação:")
        st.table(data.head(20))  # Exibir os 20 primeiros registros como tabela

        # Exibir as colunas detectadas
        st.write("Colunas detectadas nos dados:")
        st.text(", ".join(data.columns))

        # Botão para calcular o fluxo de seiva
        if st.button("Calcular Fluxo de Seiva"):
            try:
                Q_daily, Q_monthly, df_clone = calcular_fluxo(data)
                
                # Corrigindo o uso de st.columns
                col1, = st.columns(1)  # Note a vírgula para desempacotar o tuple

                # Exibir os resultados
                with col1:
                    st.write("Fluxo Diário por Sensor:")
                    st.dataframe(Q_daily)
                
                coluna1, coluna2 = st.columns(2)
                with coluna1:
                    st.write("Fluxo Mensal por Sensor:")
                    st.dataframe(Q_monthly)
                
                with coluna2:
                    st.write("Média Mensal por Clone:")
                    st.dataframe(df_clone)

                # Download dos resultados
                st.write("Baixar resultados como CSV:")
                Q_daily_csv = Q_daily.to_csv(index=False).encode('utf-8')
                Q_monthly_csv = Q_monthly.to_csv(index=False).encode('utf-8')
                df_clone_csv = df_clone.to_csv(index=False).encode('utf-8')

                st.download_button("Baixar Fluxo Diário", data=Q_daily_csv, file_name="fluxo_diario_por_sensor.csv", mime="text/csv")
                st.download_button("Baixar Fluxo Mensal", data=Q_monthly_csv, file_name="fluxo_mensal_por_sensor.csv", mime="text/csv")
                st.download_button("Baixar Média Mensal por Clone", data=df_clone_csv, file_name="media_mensal_por_clone.csv", mime="text/csv")
            except KeyError as e:
                st.error(f"Erro ao calcular fluxo de seiva: {e}")
            except IndexError as e:
                st.error(f"Erro de índice ao calcular fluxo de seiva: {e}")
