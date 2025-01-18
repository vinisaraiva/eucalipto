import pandas as pd
import numpy as np
import openpyxl
import streamlit as st
from datetime import datetime, timedelta


def otimizar_tipos_dados(df, sensor_columns):
    """Otimiza os tipos de dados do DataFrame"""
    # Otimizar tipos numéricos
    df["HORA"] = df["HORA"].astype('int32')
    df["ANO"] = df["ANO"].astype('int16')
    df["DIAJ"] = df["DIAJ"].astype('int16')
    
    # Otimizar colunas de sensores
    for sensor in sensor_columns:
        df[sensor] = pd.to_numeric(df[sensor], errors='coerce', downcast='float')
    
    return df

def processar_ano(data_ano, sensor_columns, ano):
    """Processa os dados de um ano específico"""
    resultados_ano = {}
    
    # Filtrar horário e criar cópia otimizada
    data_filtered = data_ano[
        (data_ano["HORA"] >= 360) & 
        (data_ano["HORA"] <= 1080)
    ].copy()
    
    # Tratar valores dos sensores
    for sensor in sensor_columns:
        data_filtered[sensor] = data_filtered[sensor].astype(str)
        data_filtered[sensor] = data_filtered[sensor].replace({
            '<NA>': '0', 'nan': '0', 'NaN': '0', 'NA': '0'
        })
        data_filtered[sensor] = pd.to_numeric(
            data_filtered[sensor], 
            errors='coerce'
        ).fillna(0).clip(lower=0)

    # Converter dia juliano para mês e dia
    data_filtered[['MES', 'DIA']] = data_filtered.apply(
        lambda row: pd.Series(dia_juliano_para_mes_dia(row['ANO'], row['DIAJ'])), 
        axis=1
    )

    # Processar por mês
    for mes in sorted(data_filtered["MES"].unique()):
        resultados_ano[int(mes)] = {}
        grupo_mes = data_filtered[data_filtered["MES"] == mes]
        
        for sensor in sensor_columns:
            sensor_data = grupo_mes[["DIAJ", "DIA", "HORA", sensor]].copy()
            
            # Somatório por hora para cada dia
            soma_hora = sensor_data.groupby(["DIAJ", "HORA"])[sensor].sum()
            soma_hora_dict = {}
            for (diaj, hora), valor in soma_hora.items():
                if diaj not in soma_hora_dict:
                    soma_hora_dict[diaj] = {}
                soma_hora_dict[diaj][hora] = valor

            # Somatório por dia
            soma_dia = sensor_data.groupby("DIAJ")[sensor].sum()
            
            # Somatório do mês
            soma_mes = soma_dia.sum()

            resultados_ano[int(mes)][sensor] = {
                "Somatório Hora": soma_hora_dict,
                "Somatório Dia": soma_dia,
                "Somatório Mês": soma_mes
            }
            
            # Limpar memória
            del sensor_data
    
    return resultados_ano

def calcular_somatorios(data):
    """Função principal de cálculo de somatórios"""
    sensor_columns = [col for col in data.columns if col.startswith('SENSOR')]
    
    # Otimizar tipos de dados
    data = otimizar_tipos_dados(data, sensor_columns)
    
    resultados = {}
    # Processar ano por ano
    for ano in sorted(data["ANO"].unique()):
        # Filtrar dados do ano
        data_ano = data[data["ANO"] == ano].copy()
        
        # Processar o ano
        resultados[int(ano)] = processar_ano(data_ano, sensor_columns, ano)
        
        # Limpar memória
        del data_ano
        
    return resultados

@st.cache_data
def load_data(uploaded_file):
    try:
        # Definir tipos de dados otimizados para leitura
        dtype_dict = {
            'ANO': 'int16',
            'DIAJ': 'int16',
            'HORA': 'int32'
        }
        
        # Carregar arquivo com tipos otimizados
        if uploaded_file.name.endswith('.csv'):
            data = pd.read_csv(uploaded_file, header=None, dtype=dtype_dict)
        elif uploaded_file.name.endswith('.xlsx'):
            data = pd.read_excel(uploaded_file, header=None, dtype=dtype_dict, engine='openpyxl')
        elif uploaded_file.name.endswith('.dat'):
            data = pd.read_csv(uploaded_file, sep=r',', header=None, dtype=dtype_dict)
        else:
            st.error("Formato de arquivo não suportado. Use .dat, .csv ou .xlsx.")
            return None

        # Remover primeira coluna
        data = data.iloc[:, 1:]
        
        # Remover cabeçalho se existir
        if data.iloc[0].apply(lambda x: isinstance(x, str)).any():
            data = data.iloc[1:].reset_index(drop=True)

        # Definir nomes das colunas
        fixed_columns = ["ANO", "DIAJ", "HORA"]
        sensor_columns = [f"SENSOR{i}" for i in range(1, 11)]
        
        if len(data.columns) == len(fixed_columns) + len(sensor_columns):
            all_columns = fixed_columns + sensor_columns
        else:
            all_columns = fixed_columns + ["TEMP"] + sensor_columns

        if len(data.columns) > len(all_columns):
            data = data.iloc[:, :len(all_columns)]
        elif len(data.columns) < len(fixed_columns) + len(sensor_columns):
            st.error(f"Número de colunas insuficiente: {len(data.columns)}")
            return None

        data.columns = all_columns
        
        # Garantir que ANO seja inteiro sem decimais
        data["ANO"] = data["ANO"].astype('int16')

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
                with st.spinner('Calculando somatórios... Por favor, aguarde.'):
                    resultados = calcular_somatorios(data)

                # Exibir resultados formatados em duas colunas
                col_clone1, col_clone2 = st.columns(2)
                
                clones_sensores = {
                    "CLONE1": ["SENSOR1", "SENSOR2", "SENSOR3", "SENSOR4", "SENSOR5"],
                    "CLONE2": ["SENSOR6", "SENSOR7", "SENSOR8", "SENSOR9", "SENSOR10"]
                }

                for clone, sensors in clones_sensores.items():
                    with (col_clone1 if clone == "CLONE1" else col_clone2):
                        st.subheader(f"{clone}")
                        
                        # Processar ano por ano
                        for ano in sorted(resultados.keys()):
                            st.markdown(f"### Ano: {ano}")
                            
                            # Processar mês por mês
                            for mes in sorted(resultados[ano].keys()):
                                st.markdown(f"#### Mês: {mes}")
                                
                                # Processar cada sensor do clone
                                for sensor in sensors:
                                    if sensor in resultados[ano][mes]:
                                        dados_sensor = resultados[ano][mes][sensor]
                                        
                                        # Criar expander para cada sensor
                                        with st.expander(f"{sensor} - Total do Mês: {dados_sensor['Somatório Mês']:.2f}"):
                                            # Exibir somatórios por dia
                                            st.write("Somatórios Diários:")
                                            
                                            # Organizar dias em ordem
                                            for diaj in sorted(dados_sensor['Somatório Dia'].index):
                                                soma_dia = dados_sensor['Somatório Dia'][diaj]
                                                
                                                # Criar expander para cada dia
                                                with st.expander(f"Dia {diaj}: {soma_dia:.2f}"):
                                                    if diaj in dados_sensor['Somatório Hora']:
                                                        # Organizar horas em ordem
                                                        st.write("Somatórios por Hora:")
                                                        horas_ordenadas = sorted(
                                                            dados_sensor['Somatório Hora'][diaj].items()
                                                        )
                                                        
                                                        # Criar DataFrame para exibição organizada
                                                        dados_hora = pd.DataFrame(
                                                            [(minutos_para_hhmm(hora), valor) 
                                                             for hora, valor in horas_ordenadas],
                                                            columns=['Hora', 'Valor']
                                                        )
                                                        st.dataframe(
                                                            dados_hora.set_index('Hora'),
                                                            use_container_width=True
                                                        )
                                
                                st.markdown("---")  # Separador entre meses

            except Exception as e:
                st.error(f"Erro ao exibir resultados: {str(e)}")
                st.exception(e)  # Isso mostrará o traceback completo em desenvolvimento
