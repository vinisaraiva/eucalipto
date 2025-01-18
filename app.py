import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta

# Verificar e instalar openpyxl se necessário
def check_openpyxl():
    try:
        import openpyxl
    except ImportError:
        st.error("A biblioteca 'openpyxl' é necessária para ler arquivos Excel. Por favor, instale usando: pip install openpyxl")
        return False
    return True

# Função para carregar os dados
def load_data(uploaded_file):
    try:
        # Verificar se openpyxl está instalado para arquivos Excel
        if uploaded_file.name.endswith('.xlsx') and not check_openpyxl():
            return None

        # Tentar carregar o arquivo sem cabeçalho
        if uploaded_file.name.endswith('.csv'):
            data = pd.read_csv(uploaded_file, header=None)
        elif uploaded_file.name.endswith('.xlsx'):
            data = pd.read_excel(uploaded_file, header=None, engine='openpyxl')
        elif uploaded_file.name.endswith('.dat'):
            data = pd.read_csv(uploaded_file, sep=r',', header=None)
        else:
            st.error("Formato de arquivo não suportado. Use .dat, .csv ou .xlsx.")
            return None

        # Sempre excluir a primeira coluna
        data = data.iloc[:, 1:]

        # Verificar se a primeira linha é cabeçalho (contém strings)
        if data.iloc[0].apply(lambda x: isinstance(x, str)).any():
            data = data.iloc[1:].reset_index(drop=True)

        # Definir o cabeçalho fixo base
        fixed_columns = ["ANO", "DIAJ", "HORA"]
        sensor_columns = [f"SENSOR{i}" for i in range(1, 11)]
        
        # Verificar o número de colunas para determinar se tem temperatura
        if len(data.columns) == len(fixed_columns) + len(sensor_columns):
            all_columns = fixed_columns + sensor_columns
        else:
            all_columns = fixed_columns + ["TEMP"] + sensor_columns

        if len(data.columns) > len(all_columns):
            st.warning("O número de colunas no arquivo é maior do que o esperado. Colunas extras serão descartadas.")
            data = data.iloc[:, :len(all_columns)]
        elif len(data.columns) < len(fixed_columns) + len(sensor_columns):
            st.error(f"O número de colunas no arquivo é menor do que o mínimo esperado ({len(data.columns)} em vez de {len(fixed_columns) + len(sensor_columns)}). Verifique o arquivo.")
            return None

        # Atualizar os nomes das colunas
        data.columns = all_columns

        # Tratar valores <NA>, NaN e negativos nos sensores
        for sensor in sensor_columns:
            data[sensor] = data[sensor].astype(str)  # Converter para string primeiro
            data[sensor] = data[sensor].replace({'<NA>': '0', 'nan': '0', 'NaN': '0', 'NA': '0'})
            data[sensor] = pd.to_numeric(data[sensor], errors='coerce').fillna(0)

        return data

    except Exception as e:
        st.error(f"Erro ao carregar o arquivo: {e}")
        return None

# Função para converter dia juliano para mês
def dia_juliano_para_mes_dia(ano, diaj):
    """
    Converte dia juliano para mês e dia do calendário gregoriano.
    Considera anos bissextos.
    """
    try:
        # Converter para inteiros para garantir
        ano = int(ano)
        diaj = int(diaj)
        
        # Criar data base para o ano especificado (1º de janeiro)
        data_base = datetime(ano, 1, 1)
        
        # Adicionar os dias (subtrair 1 porque o dia juliano começa em 1)
        data = data_base + timedelta(days=diaj - 1)
        
        # Retornar mês e dia
        return data.month, data.day
    except Exception as e:
        st.error(f"Erro na conversão de data juliano: {e}")
        return None, None

# Função para calcular os somatórios
def calcular_somatorios(data):
    sensor_columns = [col for col in data.columns if col.startswith('SENSOR')]

    # Tratamento de dados - converter para tipos corretos
    data["HORA"] = data["HORA"].astype(int)
    data["ANO"] = data["ANO"].astype(int)
    data["DIAJ"] = data["DIAJ"].astype(int)

    # Filtrar dados por horário entre 06:00 e 18:00 (360 a 1080 minutos)
    data_filtered = data[(data["HORA"] >= 360) & (data["HORA"] <= 1080)].copy()
    
    # Tratar valores negativos, NaN, NA e <NA> nos sensores
    for sensor in sensor_columns:
        # Primeiro, substituir <NA> por NaN
        data_filtered[sensor] = data_filtered[sensor].replace('<NA>', np.nan)
        # Converter para numérico, forçando NaN em valores não numéricos
        data_filtered[sensor] = pd.to_numeric(data_filtered[sensor], errors='coerce')
        # Substituir valores negativos e NaN por zero
        data_filtered[sensor] = data_filtered[sensor].fillna(0)
        data_filtered[sensor] = data_filtered[sensor].replace([np.inf, -np.inf], 0)
        data_filtered[sensor] = data_filtered[sensor].apply(lambda x: max(0, float(x)))

    # Converter dia juliano para mês e dia
    data_filtered[['MES', 'DIA']] = data_filtered.apply(
        lambda row: pd.Series(dia_juliano_para_mes_dia(row['ANO'], row['DIAJ'])), 
        axis=1
    )

    resultados = {}

    # Agrupar por ano e mês e depois calcular para cada sensor
    for ano in data_filtered["ANO"].unique():
        resultados[int(ano)] = {}
        grupo_ano = data_filtered[data_filtered["ANO"] == ano]
        
        for mes in grupo_ano["MES"].unique():
            resultados[int(ano)][int(mes)] = {}
            grupo_mes = grupo_ano[grupo_ano["MES"] == mes]
            
            for sensor in sensor_columns:
                sensor_data = grupo_mes[["DIA", "HORA", sensor]]

                # Somatório por hora
                soma_hora = sensor_data.groupby("HORA")[sensor].sum()

                # Somatório por dia
                soma_dia = sensor_data.groupby("DIA")[sensor].sum()

                # Somatório do mês
                soma_mes = soma_dia.sum()

                resultados[int(ano)][int(mes)][sensor] = {
                    "Somatório Hora": soma_hora,
                    "Somatório Dia": soma_dia,
                    "Somatório Mês": soma_mes
                }

    return resultados

def minutos_para_hhmm(minutos):
    """Converte minutos em formato HH:MM"""
    horas = int(minutos // 60)
    mins = int(minutos % 60)
    return f"{horas:02d}:{mins:02d}"

# Configurar a interface do Streamlit
st.subheader("Análise de Fluxo de Seiva - Somatórios Simples", divider=True)

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

        # Botão para calcular os somatórios
        if st.button("Calcular Somatórios"):
            try:
                resultados = calcular_somatorios(data)

                # Exibir resultados formatados em duas colunas
                col_clone1, col_clone2 = st.columns(2)
                
                for clone, sensors in {"CLONE1": ["SENSOR1", "SENSOR2", "SENSOR3", "SENSOR4", "SENSOR5"],
                                     "CLONE2": ["SENSOR6", "SENSOR7", "SENSOR8", "SENSOR9", "SENSOR10"]}.items():
                    with (col_clone1 if clone == "CLONE1" else col_clone2):
                        st.subheader(f"{clone}")
                        for ano, meses in resultados.items():
                            st.write(f"Ano: {ano}")
                            for mes, sensores in meses.items():
                                st.write(f"Mês: {mes}")
                                for sensor in sensors:
                                    if sensor in sensores:
                                        st.write(f"\n{sensor}")
                                        # Primeiro o somatório do mês
                                        st.write("Somatório do Mês:")
                                        st.text(f"{sensores[sensor]['Somatório Mês']:.2f}")
                                        
                                        # Depois o somatório por dia
                                        st.write("Somatório por Dia:")
                                        st.dataframe(sensores[sensor]["Somatório Dia"].round(2))
                                        
                                        # Por último o somatório por hora
                                        st.write("Somatório por Hora:")
                                        # Converter o índice de minutos para HH:MM
                                        soma_hora = sensores[sensor]["Somatório Hora"].copy()
                                        soma_hora.index = [minutos_para_hhmm(m) for m in soma_hora.index]
                                        st.dataframe(soma_hora.round(2))
                                        
                                        st.write("---")  # Separador entre sensores

            except Exception as e:
                st.error(f"Erro ao calcular somatórios: {e}")
