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
st.markdown("연도별 읍·면·동 인구 데이터를 바탕으로 시군구별 고령화율 및 유소년 비율을 시각화합니다. **(지도의 지역을 클릭하면 인구 피라미드 팝업이 뜹니다)**")

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

# 데이터에 존재하는 연도 추출
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

# 연령별/성별 인구 집계를 위한 열 목록
male_cols = [c for c in df_year.columns if c.startswith('남_')]
female_cols = [c for c in df_year.columns if c.startswith('여_')]

for c in male_cols + female_cols:
    df_year[c] = pd.to_numeric(df_year[c], errors='coerce').fillna(0)

# 시군구별 기본 지표 집계
agg_dict = {
    '전체인구': 'sum',
    '유소년인구': 'sum',
    '고령인구': 'sum',
    '시군구': 'first',
    '시도': 'first'
}
for c in male_cols + female_cols:
    agg_dict[c] = 'sum'

grouped = df_year.groupby('sigungu_code').agg(agg_dict).reset_index()

grouped['고령화율'] = np.where(grouped['전체인구'] > 0, (grouped['고령인구'] / grouped['전체인구']) * 100, np.nan)
grouped['유소년비율'] = np.where(grouped['전체인구'] > 0, (grouped['유소년인구'] / grouped['전체인구']) * 100, np.nan)

# GeoJSON의 모든 시군구 정보 수집
geojson_records = []
for f in geojson_data['features']:
    props = f['properties']
    geojson_records.append({
        'sigungu_code': str(props['코드']),
        'geo_sigungu': props.get('시군구', '알 수 없음'),
        'geo_sido': props.get('시도', '알 수 없음')
    })
geo_df = pd.DataFrame(geojson_records)

# GeoJSON 정보 기준 전체 지역 병합
merged_df = pd.merge(geo_df, grouped, on='sigungu_code', how='left')
merged_df['시군구'] = merged_df['시군구'].fillna(merged_df['geo_sigungu'])
merged_df['시도'] = merged_df['시도'].fillna(merged_df['geo_sido'])

# 미매칭 코드 탐색
data_codes = set(grouped['sigungu_code'].unique())
geojson_codes = {f['properties']['코드']: f['properties']['시군구'] for f in geojson_data['features']}
unmatched_codes = set(geojson_codes.keys()) - data_codes

# 시도 선택 드롭다운
sido_list = ["전국"] + sorted([s for s in merged_df['시도'].dropna().unique() if s != '알 수 없음'])
selected_sido = st.sidebar.selectbox("🗺️ 시도 선택 (지역 확대)", sido_list)

# 시도 필터링
if selected_sido != "전국":
    target_df = merged_df[merged_df['시도'] == selected_sido].copy()
else:
    target_df = merged_df.copy()

# 지표 선택 설정
if "고령화율" in indicator:
    metric_col = '고령화율'
    metric_name = "고령화율 (%)"
else:
    metric_col = '유소년비율'
    metric_name = "유소년 비율 (%)"

# 요약 지표 카드 3종
valid_df = target_df.dropna(subset=[metric_col])

if len(valid_df) > 0:
    total_pop_sum = valid_df['전체인구'].sum()
    if "고령화율" in indicator:
        avg_rate = (valid_df['고령인구'].sum() / total_pop_sum * 100) if total_pop_sum > 0 else 0
    else:
        avg_rate = (valid_df['유소년인구'].sum() / total_pop_sum * 100) if total_pop_sum > 0 else 0
    
    max_row = valid_df.loc[valid_df[metric_col].idxmax()]
    min_row = valid_df.loc[valid_df[metric_col].idxmin()]
    
    col1, col2, col3 = st.columns(3)
    col1.metric(f"전국 ({selected_sido}) 평균 {metric_name.split()[0]}", f"{avg_rate:.2f}%")
    col2.metric(f"가장 높은 시군구", f"{max_row['시군구']} ({max_row[metric_col]:.2f}%)")
    col3.metric(f"가장 낮은 시군구", f"{min_row['시군구']} ({min_row[metric_col]:.2f}%)")

st.markdown("---")

# --- 지도 시각화 구간 및 색상 할당 ---
if "고령화율" in indicator:
    bins = [-1, 19, 23, 28, 38, 100]
    labels = ["19% 미만", "19% ~ 23%", "23% ~ 28%", "28% ~ 38%", "38% 이상"]
    
    target_df['구간_cat'] = pd.cut(target_df[metric_col], bins=bins, labels=labels)
    target_df['구간'] = target_df['구간_cat'].astype(str)
    target_df.loc[target_df[metric_col].isna(), '구간'] = "데이터 없음 (행정구역 개편/미비)"
    
    cat_orders = labels + ["데이터 없음 (행정구역 개편/미비)"]
    color_map = {
        "19% 미만": "#fee5d9",
        "19% ~ 23%": "#fcae91",
        "23% ~ 28%": "#fb6a4a",
        "28% ~ 38%": "#de2d26",
        "38% 이상": "#a50f15",
        "데이터 없음 (행정구역 개편/미비)": "#808080"
    }
else:
    bins = [-1, 8, 10, 12, 14, 100]
    labels = ["8% 미만", "8% ~ 10%", "10% ~ 12%", "12% ~ 14%", "14% 이상"]
    
    target_df['구간_cat'] = pd.cut(target_df[metric_col], bins=bins, labels=labels)
    target_df['구간'] = target_df['구간_cat'].astype(str)
    target_df.loc[target_df[metric_col].isna(), '구간'] = "데이터 없음 (행정구역 개편/미비)"
    
    cat_orders = labels + ["데이터 없음 (행정구역 개편/미비)"]
    color_map = {
        "8% 미만": "#eff3ff",
        "8% ~ 10%": "#bdd7e7",
        "10% ~ 12%": "#6baed6",
        "12% ~ 14%": "#3182bd",
        "14% 이상": "#08519c",
        "데이터 없음 (행정구역 개편/미비)": "#808080"
    }

# 툴팁 표시문구 설정
target_df['비율_표시'] = target_df[metric_col].apply(
    lambda x: f"{x:.2f}%" if pd.notnull(x) else "데이터 없음 (행정구역 개편/미비)"
)

fig = px.choropleth(
    target_df,
    geojson=geojson_data,
    locations='sigungu_code',
    featureidkey='properties.코드',
    color='구간',
    color_discrete_map=color_map,
    category_orders={"구간": cat_orders},
    hover_name='시군구',
    hover_data={'sigungu_code': False, '구간': False, '비율_표시': True},
    labels={'비율_표시': metric_name.split()[0]}
)

# 지도 배경 및 투명/하얀색 레이어 설정
fig.update_geos(
    fitbounds="locations",
    visible=False,
    showland=False,
    showocean=False,
    showlakes=False
)

fig.update_layout(
    margin={"r":0, "t":10, "l":0, "b":0},
    height=680,
    paper_bgcolor="white",
    plot_bgcolor="white"
)

# --- 팝업 모달 함수 (st.dialog 활용) ---
@st.dialog("📊 인구 피라미드 차트", width="large")
def show_pyramid_dialog(row_data, year):
    sigungu_name = row_data['시군구']
    sido_name = row_data['시도']
    
    st.subheader(f"📍 {sido_name} {sigungu_name} ({year}년)")
    
    if pd.isna(row_data.get('전체인구')) or row_data.get('전체인구', 0) == 0:
        st.warning("이 지역은 행정구역 개편 또는 데이터 미비로 상세 인구 데이터가 존재하지 않습니다.")
        return

    # 연령대 열 수집 및 정리 (0세 ~ 100세 이상)
    ages = []
    male_pop = []
    female_pop = []
    
    for i in range(101):
        age_str = f"{i}세" if i < 100 else "100세 이상"
        m_col = f"남_{age_str}"
        f_col = f"여_{age_str}"
        
        ages.append(age_str)
        male_pop.append(row_data.get(m_col, 0))
        female_pop.append(row_data.get(f_col, 0))

    pyramid_df = pd.DataFrame({
        '연령': ages,
        '남성': male_pop,
        '여성': female_pop
    })

    # 피라미드 그래프 생성 (남성은 음수로 설정하여 좌측 배치)
    fig_pyramid = go.Figure()

    fig_pyramid.add_trace(go.Bar(
        y=pyramid_df['연령'],
        x=-pyramid_df['남성'],
        name='남성',
        orientation='h',
        marker=dict(color='#3182bd'),
        hovertemplate='연령: %{y}<br>남성 인구: %{customdata:,}명<extra></extra>',
        customdata=pyramid_df['남성']
    ))

    fig_pyramid.add_trace(go.Bar(
        y=pyramid_df['연령'],
        x=pyramid_df['여성'],
        name='여성',
        orientation='h',
        marker=dict(color='#de2d26'),
        hovertemplate='연령: %{y}<br>여성 인구: %{x:,}명<extra></extra>'
    ))

    # X축 눈금을 양수로 표기하도록 레이아웃 조절
    max_val = max(max(male_pop), max(female_pop)) * 1.1 if max(male_pop + female_pop) > 0 else 100
    
    fig_pyramid.update_layout(
        barmode='relative',
        bargap=0.1,
        height=500,
        xaxis=dict(
            title='인구 수 (명)',
            range=[-max_val, max_val],
            tickmode='array',
            tickvals=[-max_val, -max_val/2, 0, max_val/2, max_val],
            ticktext=[f"{int(max_val):,}", f"{int(max_val/2):,}", "0", f"{int(max_val/2):,}", f"{int(max_val):,}"]
        ),
        yaxis=dict(title='연령 (1세 단위)', dtick=10),
        legend=dict(x=0.8, y=1.0)
    )

    st.plotly_chart(fig_pyramid, use_container_width=True)
    
    # 요약 수치
    total = row_data['전체인구']
    elderly = row_data['고령인구']
    youth = row_data['유소년인구']
    st.caption(f"총인구: **{int(total):,}명** | 65세 이상: **{int(elderly):,}명** ({(elderly/total*100):.1f}%) | 0~14세: **{int(youth):,}명** ({(youth/total*100):.1f}%)")


# Streamlit 이벤트 감지 차트 출력
event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points")

# 클릭 시 팝업 띄우기
if event and "selection" in event and "points" in event["selection"]:
    points = event["selection"]["points"]
    if len(points) > 0:
        point = points[0]
        # 클릭한 지점의 point_index 추출
        point_idx = point.get("point_index")
        if point_idx is not None and point_idx < len(target_df):
            selected_row = target_df.iloc[point_idx]
            show_pyramid_dialog(selected_row, selected_year)

# 하단 안내 문구
if unmatched_codes:
    unmatched_names = [geojson_codes[c] for c in unmatched_codes if c in geojson_codes]
    st.info(f"💡 **안내**: 행정구역 개편 또는 데이터 미비로 인해 경계 파일과 매칭되지 않는 일부 지역은 회색으로 표시됩니다. "
            f"(미매칭 지역 수: {len(unmatched_codes)}개 / 예: {', '.join(unmatched_names[:5])}{' 등' if len(unmatched_names) > 5 else ''})")
