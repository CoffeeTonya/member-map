import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import pydeck as pdk

st.title("ヒートマップ作成ツール")
st.write("会員一覧表をアップロードしてください")

mode = st.radio("緯度経度の取得方法を選択：", ("郵便番号から取得", "住所から取得"))

uploaded_file = st.file_uploader("CSVファイルを選択", type="csv")

@st.cache_data
def load_postcode_master():
    column_names = [
        '全国地方公共団体コード', '（旧）郵便番号', '郵便番号', '都道府県カナ',
        '市区町村カナ', '町域カナ', '都道府県名', '市区町村名', '町域名',
        '項目1', '項目2', '項目3', '項目4', '項目5', '項目6'
    ]
    return pd.read_csv('postcode/KEN_ALL.csv', encoding='cp932', header=None, names=column_names)

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
    member_list = pd.read_csv(uploaded_file, encoding='cp932', on_bad_lines='skip')
    st.write("アップロードされたデータ：", member_list.head())

    if mode == "郵便番号から取得":
        post_code = load_postcode_master()

        counts = member_list['郵便番号'].value_counts().reset_index()
        counts.columns = ['郵便番号', 'count']
        counts['郵便番号'] = counts['郵便番号'].astype(str).str.split('.').str[0].str.zfill(7)
        post_code['郵便番号'] = post_code['郵便番号'].astype(str).str.zfill(7)

        df_merged = pd.merge(counts, post_code, on='郵便番号', how='left')
        df_merged['住所'] = df_merged['都道府県名'].fillna('') + df_merged['市区町村名'].fillna('') + df_merged['町域名'].fillna('')

        df_merged['URL'] = "http://geocode.csis.u-tokyo.ac.jp/cgi-bin/simple_geocode.cgi?charset=UTF8&addr=" + df_merged['住所']
        df_merged['count'] = pd.to_numeric(df_merged['count'], errors='coerce').fillna(1)

    else:
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
