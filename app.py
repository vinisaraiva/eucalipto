import pandas as pd
import numpy as np
import openpyxl
import streamlit as st
from datetime import datetime, timedelta


def otimizar_tipos_dados(df, sensor_columns):
    """Otimiza os tipos de dados do DataFrame"""
    # Otimizar tipos numéricos
    df["HORA"] = df["HORA"].astype('int32')
    df["ANO"] = pd.to_numeric(df["ANO"], errors='coerce').astype('int16')
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
    
    # Otimizar tipos de dados e garantir que ANO seja lido corretamente
    data = otimizar_tipos_dados(data, sensor_columns)
    
    # Garantir que ANO seja inteiro e tratar possíveis valores flutuantes
    data['ANO'] = data['ANO'].astype(float).astype('int16')
    
    # Verificar os anos únicos presentes no dataset
    anos_unicos = sorted(data['ANO'].unique())
    st.write(f"Anos encontrados no arquivo: {anos_unicos}")  # Debug info
    
    resultados = {}
    # Processar ano por ano
    for ano in anos_unicos:
        # Filtrar dados do ano
        data_ano = data[data["ANO"] == ano].copy()
        st.write(f"Processando ano {ano} - {len(data_ano)} registros")  # Debug info
        
        # Processar o ano
        resultados[int(ano)] = processar_ano(data_ano, sensor_columns, ano)
        
        # Limpar memória
        del data_ano
        
    return resultados

def formatar_hora(hora_str):
    """
    Formata a hora adicionando : na posição correta
    Ex: 950 -> 9:50
        1110 -> 11:10
    """
    hora_str = str(hora_str).replace(',', '').replace('.', '').zfill(4)
    if len(hora_str) == 3:
        return f"{hora_str[0]}:{hora_str[1:]}"
    elif len(hora_str) == 4:
        return f"{hora_str[:2]}:{hora_str[2:]}"
    return hora_str

def formatar_hora_display(hora_str):
    """
    Formata a hora para exibição adicionando : na posição correta
    Ex: 950 -> 9:50
        1110 -> 11:10
    """
    hora_str = str(hora_str).replace(',', '').replace('.', '').zfill(4)
    if len(hora_str) == 3:
        return f"{hora_str[0]}:{hora_str[1:]}"
    elif len(hora_str) == 4:
        return f"{hora_str[:2]}:{hora_str[2:]}"
    return hora_str

@st.cache_data
def load_data(uploaded_file):
    try:
        # Carregar arquivo sem tratamento inicial de decimais
        if uploaded_file.name.endswith('.csv'):
            data = pd.read_csv(uploaded_file, header=None)
        elif uploaded_file.name.endswith('.xlsx'):
            data = pd.read_excel(uploaded_file, header=None)
        elif uploaded_file.name.endswith('.dat'):
            data = pd.read_csv(uploaded_file, sep=r',', header=None)
        else:
            st.error("Formato de arquivo não suportado. Use .dat, .csv ou .xlsx.")
            return None

        # Remover primeira coluna (índice)
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

        # Tratar ANO - remover qualquer formatação e garantir formato YYYY
        data['ANO'] = data['ANO'].astype(str).str.replace(',', '').str.replace('.', '')
        data['ANO'] = pd.to_numeric(data['ANO'], errors='coerce').astype('int16')
        
        # Tratar HORA - manter como número para cálculos
        data['HORA'] = data['HORA'].astype(str).str.replace(',', '').str.replace('.', '')
        data['HORA'] = pd.to_numeric(data['HORA'], errors='coerce').astype('int32')
        
        # Criar coluna de hora formatada para exibição
        data['HORA_DISPLAY'] = data['HORA'].apply(formatar_hora_display)
        
        # Tratar DIAJ normalmente
        data['DIAJ'] = pd.to_numeric(data['DIAJ'], errors='coerce').astype('int16')

        # Converter valores dos sensores, mantendo vírgulas como decimais
        for sensor in sensor_columns:
            if sensor in data.columns:
                data[sensor] = pd.to_numeric(
                    data[sensor].astype(str).str.replace(',', '.'), 
                    errors='coerce'
                )

        # Verificar se os valores estão corretos
        if not all(data['ANO'].between(2000, 2100)):
            st.error("Erro: Valores inválidos na coluna ANO")
            return None

        return data

    except Exception as e:
        st.error(f"Erro ao carregar o arquivo: {e}")
        st.exception(e)
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
    data = load_data(data_file)
    if data is not None:
        # Exibir apenas uma vez as 20 primeiras linhas
        st.write("Visualização das primeiras 20 linhas dos dados:")
        st.dataframe(data.head(20))
        
        # Obter anos únicos
        anos_unicos = sorted(data['ANO'].unique())
        st.write("Selecione o ano para calcular os somatórios:")
        
        # Criar botões horizontalmente sem colunas
        for ano in anos_unicos:
            if st.button(f"Ano {ano}", key=f"btn_{ano}"):
                try:
                    with st.spinner(f'Calculando somatórios para o ano {ano}... Por favor, aguarde.'):
                        # Filtrar dados do ano selecionado
                        data_ano = data[data['ANO'] == ano].copy()
                        resultados = calcular_somatorios(data_ano)

                        # Criar duas colunas para exibição dos resultados
                        st.markdown("### Resultados")
                        col_clone1, col_clone2 = st.columns(2)
                        
                        clones_sensores = {
                            "CLONE1": ["SENSOR1", "SENSOR2", "SENSOR3", "SENSOR4", "SENSOR5"],
                            "CLONE2": ["SENSOR6", "SENSOR7", "SENSOR8", "SENSOR9", "SENSOR10"]
                        }

                        for clone, sensors in clones_sensores.items():
                            with (col_clone1 if clone == "CLONE1" else col_clone2):
                                st.subheader(f"{clone}")
                                
                                # Processar mês por mês para o ano selecionado
                                for mes in sorted(resultados[ano].keys()):
                                    st.markdown(f"#### Mês: {mes}")
                                    
                                    # Processar cada sensor do clone
                                    for sensor in sensors:
                                        if sensor in resultados[ano][mes]:
                                            dados_sensor = resultados[ano][mes][sensor]
                                            
                                            # Cabeçalho do sensor com total do mês
                                            st.markdown(f"**{sensor}** - Total do Mês: {dados_sensor['Somatório Mês']:.2f}")
                                            
                                            # Tab para dias e horas
                                            tab_dias, tab_horas = st.tabs(["Somatório por Dia", "Detalhes por Hora"])
                                            
                                            with tab_dias:
                                                # Criar DataFrame para os dias
                                                dias_df = pd.DataFrame(
                                                    dados_sensor['Somatório Dia']
                                                ).reset_index()
                                                dias_df.columns = ['Dia', 'Valor']
                                                st.dataframe(
                                                    dias_df.sort_values('Dia'),
                                                    use_container_width=True
                                                )
                                            
                                            with tab_horas:
                                                # Seletor para escolher o dia
                                                dias_disponiveis = sorted(dados_sensor['Somatório Dia'].index)
                                                dia_selecionado = st.selectbox(
                                                    f"Selecione o dia para ver as horas ({sensor})",
                                                    dias_disponiveis
                                                )
                                                
                                                if dia_selecionado in dados_sensor['Somatório Hora']:
                                                    # Criar DataFrame para as horas do dia selecionado
                                                    horas_ordenadas = sorted(
                                                        dados_sensor['Somatório Hora'][dia_selecionado].items()
                                                    )
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
                    st.exception(e)
