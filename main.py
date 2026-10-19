import io
import zipfile
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
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
    code_str = code_str.zfill(10) # 10자리 코드 맞춤
    sigungu = code_str[:5]
    
    if sigungu == '47720':
        sigungu = '27720'
    elif sigungu.startswith('42'):
        sigungu = '51' + sigungu[2:]
    elif sigungu.startswith('45'):
        sigungu = '52' + sigungu[2:]
        
    return sigungu

df['sigungu_code'] = df['코드'].apply(fix_code)

# 데이터에 존재하는 연도 추출
if '연도' in df.columns:
    df['연도_num'] = pd.to_numeric(df['연도'].astype(str).str.extract(r'(\d{4})')[0], errors='coerce')
    available_years = sorted(df['연도_num'].dropna().unique().astype(int))
else:
    available_years = [2026]
    df['연도_num'] = 2026

# 사이드바 / 컨트롤러 영역
st.sidebar.header("⚙️ 검색 및 필터 옵션")

# 1. 지표 선택
indicator = st.sidebar.radio(
    "📊 분석 지표 선택",
    ["고령화율 (65세 이상)", "유소년 비율 (0~14세)"]
)

# 2. 연도 선택 슬라이더
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

# 선택된 연도로 데이터 필터링
df_year = df[df['연도_num'] == selected_year].copy()

# 열 카테고리 구분
total_cols = [c for c in df_year.columns if c.startswith('계_')]

# 유소년(0~14세) 및 고령자(65세 이상) 열 구분
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

# 숫자형 변환
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

grouped['고령화율'] = np.where(grouped['전체인구'] > 0, (grouped['고령인구'] / grouped['전체인구']) * 100, 0)
grouped['유소년비율'] = np.where(grouped['전체인구'] > 0, (grouped['유소년인구'] / grouped['전체인구']) * 100, 0)

# 시도 선택 드롭다운
sido_list = ["전국"] + sorted(grouped['시도'].dropna().unique().tolist())
selected_sido = st.sidebar.selectbox("🗺️ 시도 선택 (지역 확대)", sido_list)

# 시도 필터링
if selected_sido != "전국":
    target_df = grouped[grouped['시도'] == selected_sido].copy()
else:
    target_df = grouped.copy()

# 지표 설정 (고령화율 vs 유소년비율)
if "고령화율" in indicator:
    metric_col = '고령화율'
    metric_name = "고령화율 (%)"
    color_scale = "Reds"
else:
    metric_col = '유소년비율'
    metric_name = "유소년 비율 (%)"
    color_scale = "Blues"

# --- 요약 지표 카드 3종 ---
if len(target_df) > 0:
    total_pop_sum = target_df['전체인구'].sum()
    if "고령화율" in indicator:
        avg_rate = (target_df['고령인구'].sum() / total_pop_sum * 100) if total_pop_sum > 0 else 0
    else:
        avg_rate = (target_df['유소년인구'].sum() / total_pop_sum * 100) if total_pop_sum > 0 else 0
    
    max_row = target_df.loc[target_df[metric_col].idxmax()]
    min_row = target_df.loc[target_df[metric_col].idxmin()]
    
    col1, col2, col3 = st.columns(3)
    col1.metric(f"전국 ({selected_sido}) 평균 {metric_name.split()[0]}", f"{avg_rate:.2f}%")
    col2.metric(f"가장 높은 시군구", f"{max_row['시군구']} ({max_row[metric_col]:.2f}%)")
    col3.metric(f"가장 낮은 시군구", f"{min_row['시군구']} ({min_row[metric_col]:.2f}%)")

st.markdown("---")

# GeoJSON의 모든 시군구 코드 수집
geojson_codes = {f['properties']['코드']: f['properties']['시군구'] for f in geojson_data['features']}
data_codes = set(grouped['sigungu_code'].unique())
unmatched_codes = set(geojson_codes.keys()) - data_codes

# --- 지도 시각화 설정 ---
if "고령화율" in indicator:
    # 19%, 23%, 28%, 38% 고정 구간 범주화
    bins = [-1, 19, 23, 28, 38, 100]
    labels = ["19% 미만", "19% ~ 23%", "23% ~ 28%", "28% ~ 38%", "38% 이상"]
    target_df['구간'] = pd.cut(target_df[metric_col], bins=bins, labels=labels)
    
    # 범주형 구간 색상 배치
    color_discrete_map = {
        "19% 미만": "#fee5d9",
        "19% ~ 23%": "#fcae91",
        "23% ~ 28%": "#fb6a4a",
        "28% ~ 38%": "#de2d26",
        "38% 이상": "#a50f15"
    }
    
    fig = px.choropleth(
        target_df,
        geojson=geojson_data,
        locations='sigungu_code',
        featureidkey='properties.코드',
        color='구간',
        color_discrete_map=color_discrete_map,
        category_orders={"구간": labels},
        hover_name='시군구',
        hover_data={'sigungu_code': False, metric_col: ':.2f%'}
    )
else:
    # 유소년 비율: 연속형 스케일 사용
    fig = px.choropleth(
        target_df,
        geojson=geojson_data,
        locations='sigungu_code',
        featureidkey='properties.코드',
        color=metric_col,
        color_continuous_scale=color_scale,
        hover_name='시군구',
        hover_data={'sigungu_code': False, metric_col: ':.2f%'}
    )

fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(
    margin={"r":0,"t":10,"l":0,"b":0},
    height=680
)

st.plotly_chart(fig, use_container_width=True)

# 안 맞는 지역(회색 미매칭 지역) 안내 문구
if unmatched_codes:
    unmatched_names = [geojson_codes[c] for c in unmatched_codes if c in geojson_codes]
    st.info(f"💡 **안내**: 행정구역 개편 또는 데이터 미비로 인해 경계 파일과 매칭되지 않는 일부 지역은 회색으로 표시됩니다. "
            f"(미매칭 지역 수: {len(unmatched_codes)}개 / 예: {', '.join(unmatched_names[:5])}{' 등' if len(unmatched_names) > 5 else ''})")
