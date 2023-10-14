import streamlit as st
import json

@st.cache_resource
def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

question = load_json("data/R4/question.json")
answer = load_json("data/R4/answer.json")

st.title(question["title"], anchor="top")

sb = st.sidebar

with sb:
    scoring = st.toggle("採点")

mark = {True:"✅", False:"❌", None:""}

headers = []
i = 0

for block in question["questions"]:
    flag = None
    title = block["title"]
    title_repr = f"{title['category']} {title['num']}"
    st.header(title_repr, anchor=str(i))
    st.write(block["text"])
    if "iroha_items" in block:
        for item in block["iroha_items"]:
            st.caption(f"* **{item['id']}** {item['text']}")

    
    options_id = [o["id"] for o in block["options"]]

    def format_option(o_id, options):
        text = [o["text"] for o in options if o["id"] == o_id][0]
        return f" **{o_id}** {text}"

    selected = st.radio("回答", options_id, index=None, key=f"{title_repr}", horizontal=False,
                        format_func=lambda o_id:format_option(o_id, block["options"]))

    if scoring:
        category = [c for c in answer["data"] if c["category"] == title["category"]][0]
        ans = [a for a in category["answers"] if a["num"] == title["num"]][0]["answer"]
        if selected:
            res = ["残念", "正解"]
            flag =ans == selected
            st.write(f"{res[flag]}{mark[flag]}")
    elif selected:
        flag = True

    headers.append((title_repr,str(i), flag))
    i += 1

score = sum([h[2] == True for h in headers])


# with st.sidebar:
with sb:
    st.markdown("[上へ戻る🏠](#top)")
    st.write(f"{score} / {len(headers)}")

    for h,i,f in headers:
        st.markdown(f"[{h}](#{i}) {mark[f]}")

with sb:
    st.write("end")