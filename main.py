import io
import zipfile
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="전국 인구구조 단계구분도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시군구 인구 지표 단계구분도")
st.markdown("연도별 읍·면·동 인구 데이터를 바탕으로 시군구별 고령화율 및 유소년 비율을 시각화합니다.")

@st.cache_data
def load_data():
    # 1. 인구 데이터 다운로드
    pop_url = "https://raw.githubusercontent.com/first2022-cyber/contents//main/population_ts_yearly_gender.zip"
    res = requests.get(pop_url)
    z = zipfile.ZipFile(io.BytesIO(res.content))
    csv_filename = z.namelist()[0]
    
    with z.open(csv_filename) as f:
        df = pd.read_csv(f, dtype={'코드': str})
        
    # 2. GeoJSON 경계 데이터 다운로드
    geojson_url = "https://raw.githubusercontent.com/first2022-cyber/contents//main/sigungu_kr.geojson"
    geo_res = requests.get(geojson_url)
    geojson_data = geo_res.json()
    
    return df, geojson_data

with st.spinner("데이터를 불러오는 중입니다... 잠시만 기다려주세요."):
    df, geojson_data = load_data()

# 데이터 전처리 및 연도 추출
df['코드'] = df['코드'].astype(str)

# 코드 개편 보정 규칙 적용
# 1) 앞 2자리 시도 코드 보정 (42 -> 51, 45 -> 52)
# 2) 군위군 보정 (47720 -> 27720)
def fix_code(code_str):
    code_str = code_str.zfill(10)
    sigungu = code_str[:5]
    
    if sigungu == '47720':
        sigungu = '27720'
    elif sigungu.startswith('42'):
        sigungu = '51' + sigungu[2:]
    elif sigungu.startswith('45'):
        sigungu = '52' + sigungu[2:]
        
    return sigungu

df['sigungu_code'] = df['코드'].apply(fix_code)

# 연도 추출
if '연도' in df.columns:
    df['연도_num'] = pd.to_numeric(df['연도'].astype(str).str.extract(r'(\d{4})')[0], errors='coerce')
    available_years = sorted(df['연도_num'].dropna().unique().astype(int))
else:
    available_years = [2026]
    df['연도_num'] = 2026

# 사이드바 컨트롤
st.sidebar.header("⚙️ 검색 및 필터 옵션")

# 1. 지표 선택
indicator = st.sidebar.radio(
    "📊 분석 지표 선택",
    ["고령화율 (65세 이상)", "유소년 비율 (0~14세)"]
)

# 2. 연도 선택
if available_years:
    selected_year = st.sidebar.slider(
        "📅 연도 선택",
        min_value=int(min(available_years)),
        max_value=int(max(available_years)),
        value=int(max(available_years)),
        step=1
    )
else:
    selected_year = 2026

# 선택 연도 필터링
df_year = df[df['연도_num'] == selected_year].copy()

total_cols = [c for c in df_year.columns if c.startswith('계_')]

youth_cols = []
elderly_cols = []

for c in total_cols:
    parts = c.replace('계_', '').replace('세', '').replace(' 이상', '')
    if parts.isdigit():
        age = int(parts)
        if age <= 14:
            youth_cols.append(c)
        elif age >= 65:
            elderly_cols.append(c)

for c in total_cols:
    df_year[c] = pd.to_numeric(df_year[c], errors='coerce').fillna(0)

# 시군구 단위 집계
df_year['전체인구'] = df_year[total_cols].sum(axis=1)
df_year['유소년인구'] = df_year[youth_cols].sum(axis=1)
df_year['고령인구'] = df_year[elderly_cols].sum(axis=1)

grouped = df_year.groupby('sigungu_code').agg({
    '전체인구': 'sum',
    '유소년인구': 'sum',
    '고령인구': 'sum',
    '시군구': 'first',
    '시도': 'first'
}).reset_index()

grouped['고령화율'] = np.where(grouped['전체인구'] > 0, (grouped['고령인구'] / grouped['전체인구']) * 100, np.nan)
grouped['유소년비율'] = np.where(grouped['전체인구'] > 0, (grouped['유소년인구'] / grouped['전체인구']) * 100, np.nan)

# GeoJSON 내 모든 시군구 목록 기반 기본 데이터프레임 생성 (미매칭 지역 채우기용)
geojson_features = []
for f in geojson_data['features']:
    props = f['properties']
    geojson_features.append({
        'sigungu_code': str(props['코드']),
        'geo_sigungu': props.get('시군구', '알 수 없음'),
        'geo_sido': props.get('시도', '알 수 없음')
    })
geo_df = pd.DataFrame(geojson_features)

# GeoJSON 기반으로 데이터 병합 (모든 지형 유지)
merged_df = pd.merge(geo_df, grouped, on='sigungu_code', how='left')

# 이름/시도 정보 보정
merged_df['시군구'] = merged_df['시군구'].fillna(merged_df
