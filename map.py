import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import pydeck as pdk

st.title("ヒートマップ作成ツール")
st.write("会員一覧表をアップロードしてください（住所情報が必要です）")

uploaded_file = st.file_uploader("CSVファイルを選択", type="csv")

def get_lat_lng_from_xml(url):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            lat = root.findtext('.//latitude')
            lng = root.findtext('.//longitude')
            return lat, lng
        else:
            return None, None
    except Exception:
        return None, None

if uploaded_file is not None:
    member_list = pd.read_csv(uploaded_file, encoding='cp932', skiprows=[1], on_bad_lines='skip')
    st.write("アップロードされたデータ：", member_list.head())

    # フィルター対象列の確認と選択肢表示（サイドバー）
    filter_columns = ['入会ショップ', '性別', '会員ランク', '累計購入回数', '最終適用利用店舗']
    available_filters = [col for col in filter_columns if col in member_list.columns]

    selected_filters = {}
    if available_filters:
        with st.sidebar:
            st.subheader("データの表示切替")
            for col in available_filters:
                if col == '累計購入回数':
                    member_list[col] = pd.to_numeric(member_list[col], errors='coerce')
                    min_val = int(member_list[col].min(skipna=True))
                    max_val = int(member_list[col].max(skipna=True))
                    selected_range = st.slider(f"{col} の範囲を選択", min_val, max_val, (min_val, max_val))
                    member_list = member_list[(member_list[col] >= selected_range[0]) & (member_list[col] <= selected_range[1])]
                else:
                    options = member_list[col].dropna().unique().tolist()
                    selected = st.multiselect(f"{col} を選択", options, default=options)
                    selected_filters[col] = selected

            for col, selected in selected_filters.items():
                member_list = member_list[member_list[col].isin(selected)]

    # 住所を構築
    member_list['住所'] = (
        member_list['都道府県'].fillna('') +
        member_list['市区町村'].fillna('') +
        member_list['町域'].fillna('') +
        member_list['番地'].fillna('')
    )
    member_list['count'] = 1
    member_list['URL'] = "http://geocode.csis.u-tokyo.ac.jp/cgi-bin/simple_geocode.cgi?charset=UTF8&addr=" + member_list['住所']
    df_merged = member_list

    st.write("緯度経度を取得中...")
    latitudes = []
    longitudes = []
    progress = st.progress(0)
    total = len(df_merged)

    for i, url in enumerate(df_merged['URL']):
        lat, lng = get_lat_lng_from_xml(url)
        latitudes.append(lat)
        longitudes.append(lng)
        progress.progress((i + 1) / total)

    df_merged['緯度'] = latitudes
    df_merged['経度'] = longitudes
    df_result = df_merged[['緯度', '経度', 'count']].copy()

    df_result['緯度'] = pd.to_numeric(df_result['緯度'], errors='coerce')
    df_result['経度'] = pd.to_numeric(df_result['経度'], errors='coerce')
    df_result['count'] = pd.to_numeric(df_result['count'], errors='coerce').fillna(0)
    df_result = df_result.dropna(subset=['緯度', '経度'])

    st.success("緯度・経度の取得が完了しました！")
    # st.dataframe(df_result)

    csv = df_result.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("CSVをダウンロード", data=csv, file_name='output_with_latlng.csv', mime='text/csv')

    if {'緯度', '経度', 'count'}.issubset(df_result.columns):
        midpoint = [df_result["緯度"].mean(), df_result["経度"].mean()]
        japanese_map_style = "https://tile.openstreetmap.jp/styles/osm-bright-ja/style.json"

        st.pydeck_chart(pdk.Deck(
            map_style=japanese_map_style,
            initial_view_state=pdk.ViewState(
                latitude=midpoint[0],
                longitude=midpoint[1],
                zoom=12,
                pitch=0,
                bearing=0
            ),
            layers=[
                pdk.Layer(
                    "HeatmapLayer",
                    data=df_result,
                    get_position='[経度, 緯度]',
                    get_weight='count',
                    radiusPixels=80,
                )
            ]
        ))
    else:
        st.error("'緯度', '経度', 'count' の列が必要です。")
