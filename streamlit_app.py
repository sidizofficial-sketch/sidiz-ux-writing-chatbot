import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. 페이지 설정 (가장 먼저)
# ==========================================
st.set_page_config(page_title="시디즈 UX 번역기", page_icon="💺")

# ==========================================
# 2. 보안 설정
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # 사용 가능한 모델 찾기
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    
    st.success(f"✅ 모델 로드 완료: {target}")
    
except KeyError:
    st.error("❌ Secrets에 'gemini.api_key'가 설정되지 않았습니다.")
    st.stop()
except Exception as e:
    st.error(f"❌ Gemini API 초기화 오류: {e}")
    st.stop()

# ==========================================
# 3. 브랜드 가
