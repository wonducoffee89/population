import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go


# =========================================================
# 1. 기본 설정
# =========================================================

st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide",
)

# 따뜻한 색감으로 화면을 꾸밉니다.
st.markdown(
    """
    <style>
        .stApp {
            background-color: #FFF9F2;
        }
        h1, h2, h3 {
            color: #70452F;
        }
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #F0DCCB;
            padding: 16px;
            border-radius: 12px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 2. 데이터 불러오기
# =========================================================

DATA_URL = (
    "https://raw.githubusercontent.com/"
    "greatsong/modudata/main/data/population_yearly.csv.gz"
)


@st.cache_data
def load_data():
    # pandas는 gzip으로 압축된 CSV 파일을 바로 읽을 수 있습니다.
    data = pd.read_csv(DATA_URL, compression="gzip")

    # 열 이름의 앞뒤 공백을 제거합니다.
    data.columns = data.columns.astype(str).str.strip()

    # 연도 열을 숫자로 변환하고, 연도가 없는 행은 제외합니다.
    data["연도"] = pd.to_numeric(data["연도"], errors="coerce")
    data = data.dropna(subset=["연도"]).copy()
    data["연도"] = data["연도"].astype(int)

    # 데이터에 실제로 들어 있는 가장 최신 연도만 사용합니다.
    latest_year = int(data["연도"].max())
    data = data[data["연도"] == latest_year].copy()

    # 지역 이름의 앞뒤 공백을 제거합니다.
    for column in ["시도", "시군구", "동"]:
        data[column] = data[column].astype("string").str.strip()

    return data, latest_year


st.title("🏘️ 동네별 인구 피라미드")
st.markdown(
    """
    우리 동네에는 연령대별로 얼마나 많은 사람이 살고 있을까요?
    시도, 시군구, 동을 선택해 남녀 인구 구성과 인구 지표를 살펴보세요.
    """
)

try:
    with st.spinner("인구 데이터를 불러오는 중입니다..."):
        df, latest_year = load_data()
except Exception as error:
    st.error("인구 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
    st.caption(f"오류 내용: {error}")
    st.stop()

if df.empty:
    st.warning("최신 연도에 해당하는 데이터가 없습니다.")
    st.stop()


# =========================================================
# 3. 지역 선택: 시도 → 시군구 → 동
# =========================================================

st.subheader("📍 우리 동네 선택")

col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df["시도"].dropna().unique().tolist())
    if not sido_list:
        st.warning("선택할 시도 데이터가 없습니다.")
        st.stop()
    selected_sido = st.selectbox("① 시도", options=sido_list)

# 선택한 시도에 속한 시군구만 보여 줍니다.
sido_df = df[df["시도"] == selected_sido].copy()

with col2:
    sigungu_list = sorted(sido_df["시군구"].dropna().unique().tolist())
    if not sigungu_list:
        st.warning("선택한 시도에 시군구 데이터가 없습니다.")
        st.stop()
    selected_sigungu = st.selectbox("② 시군구", options=sigungu_list)

# 선택한 시군구에 속한 동만 보여 줍니다.
sigungu_df = sido_df[sido_df["시군구"] == selected_sigungu].copy()

with col3:
    dong_list = sorted(sigungu_df["동"].dropna().unique().tolist())
    if not dong_list:
        st.warning("선택한 시군구에 동 데이터가 없습니다.")
        st.stop()
    selected_dong = st.selectbox("③ 동", options=dong_list)


# =========================================================
# 4. 선택한 동네의 데이터 찾기
# =========================================================

selected_df = df[
    (df["시도"] == selected_sido)
    & (df["시군구"] == selected_sigungu)
    & (df["동"] == selected_dong)
].copy()

if selected_df.empty:
    st.warning("선택한 지역의 인구 자료가 없습니다.")
    st.stop()

# 일반적으로 지역마다 한 행입니다. 중복 행이 있다면 연령별 인구를 합칩니다.
if len(selected_df) > 1:
    st.warning("같은 지역에 여러 행이 있어 연령별 인구를 합산합니다.")

    population_columns = [
        column for column in selected_df.columns
        if column.startswith("남_") or column.startswith("여_")
    ]
    row = selected_df.iloc[0].copy()
    for column in population_columns:
        row[column] = pd.to_numeric(
            selected_df[column], errors="coerce"
        ).fillna(0).sum()
else:
    row = selected_df.iloc[0]


# =========================================================
# 5. 나이별 남녀 인구 계산
# =========================================================

# 0세부터 99세까지와 마지막 '100세 이상'을 표시합니다.
age_labels = [f"{age}세" for age in range(100)] + ["100세 이상"]
male_columns = [f"남_{age}세" for age in range(100)] + ["남_100세 이상"]
female_columns = [f"여_{age}세" for age in range(100)] + ["여_100세 이상"]


def get_population(data_row, column_name):
    """인구 값을 숫자로 읽습니다. 열이 없거나 값이 비어 있으면 0으로 처리합니다."""
    if column_name not in data_row.index:
        return 0

    value = pd.to_numeric(data_row[column_name], errors="coerce")
    if pd.isna(value):
        return 0

    return max(0, int(value))


male_population = [get_population(row, col) for col in male_columns]
female_population = [get_population(row, col) for col in female_columns]

# 남자는 왼쪽으로 표시하도록 음수로 바꿉니다.
male_left = [-value for value in male_population]
# 여자는 오른쪽에 표시하도록 양수를 유지합니다.
female_right = female_population

age_population = [
    male_population[i] + female_population[i]
    for i in range(101)
]

total_male = sum(male_population)
total_female = sum(female_population)
total_population = total_male + total_female


# =========================================================
# 6. 추가 지표: 평균연령, 고령화율, 자동 설명
# =========================================================

# 평균연령은 연령별 인구를 가중치로 계산합니다.
# '100세 이상'은 계산을 위해 100세로 처리합니다.
if total_population > 0:
    average_age = sum(
        age * age_population[age]
        for age in range(101)
    ) / total_population
else:
    average_age = 0.0

# 65세 이상 인구와 전체 인구에서 차지하는 비율을 계산합니다.
elderly_population = sum(age_population[65:])
aging_rate = (
    elderly_population / total_population * 100
    if total_population > 0
    else 0.0
)

# 0~14세 아동 인구와 65세 이상 인구를 비교해 설명을 만듭니다.
child_population = sum(age_population[0:15])

if child_population > elderly_population:
    population_comment = (
        "이 동네는 65세 이상 인구보다 0~14세 아이가 더 많은 편입니다."
    )
elif child_population < elderly_population:
    population_comment = (
        "이 동네는 아이보다 65세 이상 어르신이 더 많은 편입니다."
    )
else:
    population_comment = (
        "이 동네는 0~14세 아이와 65세 이상 어르신의 인구가 같습니다."
    )

# 고령화율이 20%를 초과하는지 확인합니다.
is_aging_warning = aging_rate > 20


# =========================================================
# 7. 지표 카드 3개
# =========================================================

st.divider()
st.subheader(f"📊 {selected_sido} {selected_sigungu} {selected_dong}")
st.caption(f"기준 연도: {latest_year}년 · 데이터에 포함된 최신 연도")

metric1, metric2, metric3 = st.columns(3)

with metric1:
    st.metric(
        label="👥 총인구",
        value=f"{total_population:,}명",
    )

with metric2:
    st.metric(
        label="🎂 평균연령",
        value=f"{average_age:.1f}세",
    )

with metric3:
    # 고령화율이 20%를 넘으면 카드 옆 지표에 주의 표시를 붙입니다.
    st.metric(
        label="👵 고령화율 (65세 이상)",
        value=f"{aging_rate:.1f}%",
        delta="⚠️ 20% 초과" if is_aging_warning else "20% 이하",
        delta_color="inverse",
    )

if is_aging_warning:
    st.warning(
        f"⚠️ 고령화율이 20%를 초과했습니다. "
        f"이 동네의 65세 이상 인구 비율은 {aging_rate:.1f}%입니다."
    )


# =========================================================
# 8. 인구 피라미드 그리기
# =========================================================

fig = go.Figure()

# 남자 인구는 음수이므로 왼쪽에 표시됩니다.
fig.add_trace(
    go.Bar(
        x=male_left,
        y=age_labels,
        orientation="h",
        name="남자",
        marker_color="#D9826B",
        customdata=male_population,
        hovertemplate="나이: %{y}<br>남자 인구: %{customdata:,}명<extra></extra>",
    )
)

# 여자 인구는 양수이므로 오른쪽에 표시됩니다.
fig.add_trace(
    go.Bar(
        x=female_right,
        y=age_labels,
        orientation="h",
        name="여자",
        marker_color="#E9B66B",
        customdata=female_population,
        hovertemplate="나이: %{y}<br>여자 인구: %{customdata:,}명<extra></extra>",
    )
)

max_population = max(max(male_population), max(female_population), 1)
axis_limit = max_population * 1.1

# 좌우 축 눈금을 대칭으로 만들고, 숫자는 절댓값으로 표시합니다.
tick_step = max(1, int(np.ceil(axis_limit / 5)))
positive_ticks = list(range(0, int(axis_limit) + tick_step, tick_step))
positive_ticks = [value for value in positive_ticks if value <= axis_limit]

if not positive_ticks or positive_ticks[0] != 0:
    positive_ticks.insert(0, 0)

tick_values = (
    [-value for value in reversed(positive_ticks) if value != 0]
    + [0]
    + [value for value in positive_ticks if value != 0]
)
tick_text = [f"{abs(value):,}" for value in tick_values]

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 남녀 인구",
        "x": 0.5,
        "xanchor": "center",
    },
    barmode="overlay",
    bargap=0.12,
    height=1000,
    plot_bgcolor="#FFFDF9",
    paper_bgcolor="#FFF9F2",
    font={"family": "Arial, sans-serif", "size": 12, "color": "#5D4037"},
    legend={
        "title": "성별",
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "xanchor": "center",
        "x": 0.5,
    },
    xaxis={
        "title": "인구 (명)",
        "range": [-axis_limit, axis_limit],
        "tickmode": "array",
        "tickvals": tick_values,
        "ticktext": tick_text,
        "zeroline": True,
        "zerolinecolor": "#9E8A7C",
        "zerolinewidth": 1.5,
        "gridcolor": "#F0E4D8",
    },
    yaxis={
        "title": "나이",
        # 나이 라벨 순서를 직접 지정합니다.
        # 이 순서대로 0세가 아래, 100세 이상이 위에 표시됩니다.
        "categoryorder": "array",
        "categoryarray": age_labels,
        "autorange": True,
        "showgrid": False,
        "tickfont": {"size": 10},
    },
    margin={"l": 100, "r": 40, "t": 100, "b": 70},
)

st.plotly_chart(fig, width="stretch", config={"displayModeBar": True})


# =========================================================
# 9. 피라미드 아래 자동 설명
# =========================================================

st.info(
    "**이 동네는 아이가 많은 편인가요, 어르신이 많은 편인가요?**\n\n"
    + population_comment
)


# =========================================================
# 10. 연령별 인구 표
# =========================================================

with st.expander("📋 연령별 인구 표 보기"):
    population_table = pd.DataFrame(
        {
            "나이": age_labels,
            "남자 인구": male_population,
            "여자 인구": female_population,
            "합계": age_population,
        }
    )

    st.dataframe(
        population_table,
        hide_index=True,
        width="stretch",
    )

st.caption(
    "자료: 제공된 연도별 읍·면·동 인구 CSV | "
    "남자는 왼쪽, 여자는 오른쪽에 표시됩니다. "
    "평균연령 계산에서 100세 이상은 100세로 처리합니다."
)  
