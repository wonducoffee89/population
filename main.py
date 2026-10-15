import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 디자인 (따뜻한 톤 스타일링)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="👨‍👩‍👧‍👦",
    layout="wide",
)

# 따뜻한 톤 스타일 커스텀 CSS 적용
st.markdown(
    """
    <style>
    /* 전체 배경색 및 기본 글꼴 설정 */
    .main {
        background-color: #FAF7F2;
    }
    /* 카드/컨테이너 배경 */
    div[data-testid="stBlock"] {
        background-color: #FFFDF9;
        border-radius: 10px;
        padding: 15px;
    }
    /* 타이틀 색상 */
    h1 {
        color: #5A4035;
        font-weight: 700;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 및 전처리 (캐시 적용)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    """지정된 GitHub URL에서 ZIP 압축 CSV 데이터를 읽어오고 최신 연도 데이터를 추출합니다."""
    # 본인의 GitHub 유저네임으로 url의 'first2022-cyber' 부분을 교체해 주세요.
    url = "https://raw.githubusercontent.com/first2022-cyber/contents/main/population_ts_yearly_gender.zip"

    # 판다스로 ZIP 내 CSV 데이터 직접 읽기 (UTF-8 또는 EUC-KR 인코딩 처리)
    try:
        df = pd.read_csv(url, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(url, encoding="euc-kr")

    # '연도' 열에서 가장 최신 연도 찾기 및 최신 연도 데이터 필터링
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    return df_latest, latest_year


# 데이터 로딩 실행
try:
    df, latest_year = load_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 메인 화면 헤더
# -----------------------------------------------------------------------------
st.title("👨‍👩‍👧‍👦 동네별 인구 피라미드")
st.write(
    f"우리 동네의 나이별·성별 인구 구조를 한눈에 확인해보세요. (기준 연도: **{latest_year}년**)"
)
st.markdown("---")

# -----------------------------------------------------------------------------
# 4. 드롭다운 선택 상자 (시도 -> 시군구 -> 동)
# -----------------------------------------------------------------------------
st.subheader("📍 지역 선택")
col1, col2, col3 = st.columns(3)

# 1) 시도 선택
sido_list = sorted(df["시도"].dropna().unique())
with col1:
    selected_sido = st.selectbox("시·도 선택", sido_list)

# 선택한 시도에 해당하는 데이터 필터링
df_sido = df[df["시도"] == selected_sido]

# 2) 시군구 선택
sigungu_list = sorted(df_sido["시군구"].dropna().unique())
with col2:
    selected_sigungu = st.selectbox("시·군·구 선택", sigungu_list)

# 선택한 시군구에 해당하는 데이터 필터링
df_sigungu = df_sido[df_sido["시군구"] == selected_sigungu]

# 3) 동 선택
dong_list = sorted(df_sigungu["동"].dropna().unique())
with col3:
    selected_dong = st.selectbox("읍·면·동 선택", dong_list)

# 최종 선택된 지역의 1개 행 추출
selected_row = df_sigungu[df_sigungu["동"] == selected_dong].iloc[0]

# -----------------------------------------------------------------------------
# 5. 인구 데이터 정리 및 통계 지표 계산
# -----------------------------------------------------------------------------
# 나이 라벨 생성 (0세 ~ 99세, 100세 이상)
age_labels = [f"{i}세" for i in range(100)] + ["100세 이상"]

male_pop = []  # 남자 인구수 (음수로 저장)
female_pop = []  # 여자 인구수 (양수로 저장)
age_values = list(range(100)) + [100]  # 평균 나이 계산용 숫자 리스트 (100세 이상은 100으로 계산)

total_population = 0
total_age_sum = 0
elderly_population = 0  # 65세 이상 인구
child_population = 0  # 14세 이하 유소년 인구

for idx, age in enumerate(age_labels):
    m_col = f"남_{age}"
    f_col = f"여_{age}"

    m_val = int(selected_row.get(m_col, 0))
    f_val = int(selected_row.get(f_col, 0))

    # 그래프용 데이터 (남자는 음수, 여자는 양수)
    male_pop.append(-m_val)
    female_pop.append(f_val)

    # 나이별 합계 인구
    pop_at_age = m_val + f_val
    total_population += pop_at_age

    # 평균 연령 계산을 위한 총 나이 합산
    total_age_sum += pop_at_age * age_values[idx]

    # 고령 인구(65세 이상) 계산
    if age_values[idx] >= 65:
        elderly_population += pop_at_age

    # 유소년 인구(0세~14세) 계산
    if age_values[idx] <= 14:
        child_population += pop_at_age

# 주요 지표 계산
avg_age = total_age_sum / total_population if total_population > 0 else 0
elderly_ratio = (
    (elderly_population / total_population) * 100
    if total_population > 0
    else 0
)

# -----------------------------------------------------------------------------
# 6. 지표 카드 3개 나란히 표시 (그래프 위)
# -----------------------------------------------------------------------------
st.markdown("### 📊 주요 인구 지표")
m_col1, m_col2, m_col3 = st.columns(3)

m_col1.metric("총인구", f"{total_population:,} 명")
m_col2.metric("평균연령", f"{avg_age:.1f} 세")

# 고령화율 20% 이상일 때 경고 라벨/주의 표시 붙이기
if elderly_ratio >= 20.0:
    m_col3.metric(
        "고령화율 (65세 이상)",
        f"{elderly_ratio:.1f} %",
        delta="⚠️ 초고령사회 (20% 초과)",
        delta_color="inverse",
    )
else:
    m_col3.metric("고령화율 (65세 이상)", f"{elderly_ratio:.1f} %")

st.markdown("---")

# -----------------------------------------------------------------------------
# 7. Plotly 인구 피라미드 가로 막대그래프 생성
# -----------------------------------------------------------------------------
fig = go.Figure()

# 남자 데이터 (왼쪽, 음수값) - 따뜻한 올리브 그린
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=male_pop,
        name="남자",
        orientation="h",
        marker=dict(color="#6B8E23"),
        hovertemplate="남자 %{y}: %{customdata}명<extra></extra>",
        customdata=[abs(x) for x in male_pop],
    )
)

# 여자 데이터 (오른쪽, 양수값) - 따뜻한 테라코타 붉은색
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=female_pop,
        name="여자",
        orientation="h",
        marker=dict(color="#E07A5F"),
        hovertemplate="여자 %{y}: %{x}명<extra></extra>",
    )
)

# 축 레이아웃 지정 및 나이 축(0세~100세 이상) 순서 고정
fig.update_layout(
    title=dict(
        text=f"<b>{selected_sido} {selected_sigungu} {selected_dong}</b> 인구 피라미드",
        font=dict(size=20, color="#5A4035"),
        x=0.5,
        xanchor="center",
    ),
    barmode="overlay",
    bargap=0.1,
    paper_bgcolor="#FFFDF9",
    plot_bgcolor="#FFFDF9",
    height=750,
    legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
    ),
    xaxis=dict(
        title="인구수 (명)",
        tickmode="array",
        tickvals=[
            -10000,
            -5000,
            -2000,
            -1000,
            -500,
            0,
            500,
            1000,
            2000,
            5000,
            10000,
        ],
        ticktext=[
            "10,000",
            "5,000",
            "2,000",
            "1,000",
            "500",
            "0",
            "500",
            "1,000",
            "2,000",
            "5,000",
            "10,000",
        ],
        gridcolor="#EFEAE1",
    ),
    yaxis=dict(
        title="나이",
        type="category",
        categoryorder="array",
        categoryarray=age_labels,
        gridcolor="#EFEAE1",
        dtick=5,
    ),
)

# 그래프 화면 출력
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 8. 피라미드 아래 자동 분석 한 줄 설명
# -----------------------------------------------------------------------------
st.markdown("### 💡 이 동네는 아이가 많은 편인가요, 어르신이 많은 편인가요?")

# 아이(0~14세) 및 어르신(65세 이상) 비율 계산
child_ratio = (
    (child_population / total_population) * 100 if total_population > 0 else 0
)

# 동네 특성 분석 메시지 자동 작성
if elderly_ratio >= 20.0 and child_ratio < 10.0:
    analysis_text = f"이 동네는 어르신(65세 이상) 비율이 **{elderly_ratio:.1f}%**로 매우 높고, 아이(0~14세) 비율은 **{child_ratio:.1f}%**로 낮아 **어르신들이 주로 거주하시는 동네**입니다. 👴👵"
elif child_ratio > elderly_ratio:
    analysis_text = f"이 동네는 아이(0~14세) 비율이 **{child_ratio:.1f}%**로 어르신 비율(**{elderly_ratio:.1f}%**)보다 높아 **아이들과 젊은 세대가 비교적 많은 활기찬 동네**입니다. 👶🧒"
elif elderly_ratio > child_ratio:
    analysis_text = f"이 동네는 어르신(65세 이상) 비율이 **{elderly_ratio:.1f}%**로 아이 비율(**{child_ratio:.1f}%**)보다 높아서 **어르신 비중이 상대적으로 높은 동네**입니다. 👵👴"
else:
    analysis_text = f"이 동네는 아이(0~14세) 비율(**{child_ratio:.1f}%**)과 어르신(65세 이상) 비율(**{elderly_ratio:.1f}%**)이 **균형을 이루고 있는 동네**입니다. 🏡"

# 안내 박스(info) 형태로 출력
st.info(analysis_text)
