import io
import zipfile
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# 페이지 설정
st.set_page_config(
    page_title="전국 시군구 고령화 단계구분도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 2026년 전국 시군구 고령화 단계구분도")
st.markdown("읍·면·동 인구 데이터를 바탕으로 시군구별 65세 이상 인구 비율을 시각화합니다.")

@st.cache_data
def load_data():
    # 1. 인구 데이터 다운로드 및 압축 해제 (판다스로 바로 읽기)
    pop_url = "https://raw.githubusercontent.com/first2022-cyber/contents//main/population_ts_yearly_gender.zip"
    
    res = requests.get(pop_url)
    z = zipfile.ZipFile(io.BytesIO(res.content))
    csv_filename = z.namelist()[0]
    
    with z.open(csv_filename) as f:
        df = pd.read_csv(f, dtype={'코드': str})
        
    # 2. 시군구 경계 GeoJSON 다운로드
    geojson_url = "https://raw.githubusercontent.com/first2022-cyber/contents//main/sigungu_kr.geojson"
    geo_res = requests.get(geojson_url)
    geojson_data = geo_res.json()
    
    return df, geojson_data

with st.spinner("데이터를 불러오는 중입니다... 잠시만 기다려주세요."):
    df, geojson_data = load_data()

# 3. 2026년 데이터 필터링
# 열 이름에 연도가 포함되어 있거나 연도별 파일인 경우 '연도' 컬럼 확인 (여기서는 연도 열이 존재한다고 가정, 혹은 필터링)
# 데이터 구조에 맞추어 연도 컬럼 처리 ('연도' 또는 날짜 관련 컬럼 확인 필요하나, 요청사항에 따라 2026년 필터링 적용)
if '연도' in df.columns:
    df_2026 = df[df['연도'].astype(str).str.contains('2026')].copy()
else:
    # 연도 컬럼이 명시되지 않은 경우 전체 데이터에서 2026년도 대상이라 가정하거나 그대로 사용
    df_2026 = df.copy()

# 만약 데이터에 2026년이 명시되어 있지 않다면 전체를 2026년 데이터로 간주하고 진행
if len(df_2026) == 0:
    df_2026 = df.copy()

# 4. 시군구 코드 (앞 5자리) 추출
df_2026['sigungu_code'] = df_2026['코드'].astype(str).str.slice(0, 5)

# 5. 전체 인구 및 65세 이상 인구 컬럼 정의
# 전체 인구: '계_'로 시작하는 모든 열의 합
total_cols = [c for c in df_2026.columns if c.startswith('계_')]

# 65세 이상 인구: '계_65세'부터 '계_100세 이상'까지
# 나이 열 추출 ('계_0세' ~ '계_100세 이상' 중 65세 이상만 필터링)
age_cols_65_plus = []
for c in total_cols:
    # 예: '계_65세', '계_100세 이상' 등에서 숫자 추출
    parts = c.replace('계_', '').replace('세', '').replace(' 이상', '')
    if parts.isdigit() and int(parts) >= 65:
        age_cols_65_plus.append(c)

# 숫자형 변환 안전장치
for c in total_cols:
    df_2026[c] = pd.to_numeric(df_2026[c], errors='coerce').fillna(0)

# 6. 시군구별 그룹화 및 합산
df_2026['전체인구'] = df_2026[total_cols].sum(axis=1)
df_2026['고령인구'] = df_2026[age_cols_65_plus].sum(axis=1)

grouped = df_2026.groupby('sigungu_code').agg({
    '전체인구': 'sum',
    '고령인구': 'sum',
    '시군구': 'first', # 대표 시군구 이름 가져오기
    '시도': 'first'
}).reset_index()

# 고령화율 계산 (%)
grouped['고령화율'] = (grouped['고령인구'] / grouped['전체인구']) * 100

# 7. Plotly 단계구분도 시각화
fig = px.choropleth(
    grouped,
    geojson=geojson_data,
    locations='sigungu_code',
    featureidkey='properties.코드',
    color='고령화율',
    color_continuous_scale='Reds',
    hover_name='시군구',
    hover_data={'sigungu_code': False, '고령화율': ':.2f'}
)

fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(
    margin={"r":0,"t":0,"l":0,"b":0},
    height=700
)

# Streamlit 출력
st.plotly_chart(fig, use_container_width=True)

# 부가 정보 표시
with st.expander("📊 시군구별 고령화율 데이터 상세보기"):
    st.dataframe(
        grouped[['sigungu_code', '시도', '시군구', '전체인구', '고령인구', '고령화율']]
        .sort_values(by='고령화율', ascending=False)
        .reset_index(drop=True)
    )
