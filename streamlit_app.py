import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. 보안 설정 (Secrets에서 키 가져오기)
# ==========================================
try:
    # Streamlit Cloud의 Secrets 설정에서 키를 읽어옵니다.
    GOOGLE_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except KeyError:
    st.error("Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다. 관리자 설정을 확인해주세요.")
    st.stop()

# ==========================================
# 2. 브랜드 가이드라인 (System Instruction)
# ==========================================
SYSTEM_INSTRUCTION = """
# To run this code you need to install the following dependencies:
# pip install google-genai

import base64
import os
from google import genai
from google.genai import types


def generate():
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-3-flash-preview"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""INSERT_INPUT_HERE"""),
            ],
        ),
    ]
    tools = [
        types.Tool(googleSearch=types.GoogleSearch(
        )),
    ]
    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level="HIGH",
        ),
        tools=tools,
        system_instruction=[
            types.Part.from_text(text="""너는 시디즈의 UX 라이터야. 일반적인 문구를 시디즈만의 [전문적/세심한/혁신적] 톤으로 바꿔줘.
아래는 시디즈 홈페이지에서 가져온 브랜드 문구들이야. 이 말투와 단어 선택을 학습해서 내 문장을 변환해줘.

[참고 문구]

시디즈의 디자인은 사용자로부터 시작됩니다.
누가 앉을지, 어떤 상황에서 쓰일지, 어떤 움직임이 의자 위에서 일어날지 끊임없이 관찰하고 고민하여 최상의 의자 위 경험이라는 시팅 솔루션을 구현해냅니다.

시디즈의 제품은 다양한 사람들을 만납니다.
시디즈는 인체에 대한 다양한 연구와 공학적 설계를 통해 누구든지 편안하게 사용할 수 있는 제품을 완성합니다.

시디즈는 기술의 발전을 앞서갑니다.
언제나 새로운 시도를 주저 않고, 쌓아온 전문성을 제품에 더해 의자 위의 가장 진보된 경험을 만듭니다.

의자를 통해 사회적 선순환을 설계합니다.
제품 사용에 대한 인식 전환과, 그를 뒷받침하는 우수한 제품력, 새로운 수리 방식을 통해 제품 구매가 기능적 가치를 넘어 지속가능성을 이루는 방식이 되도록 책임을 다합니다.

갈수록 다양해지는 디바이스와 업무 환경 속에서 당신이 변함없이 최상의 능력을 발휘할 수 있도록
어떤 상황과 자세에서도 유연하게 반응하며 모든 니즈에 대응하는 퍼포먼스 공학 의자와 함께하세요."""),
        ],
    )

    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        print(chunk.text, end="")

if __name__ == "__main__":
    generate()

"""

# ==========================================
# 3. UI 구성 및 채팅 로직
# ==========================================
st.set_page_config(page_title="시디즈 UX 번역기", page_icon="💺")
st.title("💺 시디즈 UX 라이팅 번역기")

if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화 내역 표시 및 피드백 버튼
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and i == len(st.session_state.messages) - 1:
            # 엄지척 피드백 수집
            st.feedback("thumbs", key=f"feedback_{i}")

# 사용자 입력 처리
if prompt := st.chat_input("수정할 문구를 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Gemini 모델 호출 (System Instruction 포함)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_INSTRUCTION
        )
        response = model.generate_content(prompt)
        st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        st.rerun()
