"""
Gemini API 키 테스트 스크립트

사용법:
1. Streamlit Secrets에서 API 키 복사
2. 터미널에서 실행: python test_api_key.py
"""

import google.generativeai as genai
import time

# ⚠️ 여기에 실제 API 키를 붙여넣으세요
API_KEY = "YOUR_API_KEY_HERE"

print("=" * 50)
print("Gemini API 키 테스트")
print("=" * 50)
print()

try:
    genai.configure(api_key=API_KEY)
    
    # 사용 가능한 모델 확인
    print("✅ API 키 인증 성공!")
    print()
    
    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    print(f"사용 가능한 모델: {len(models)}개")
    for model in models[:3]:
        print(f"  - {model}")
    print()
    
    # 간단한 테스트 호출
    print("테스트 호출 시작...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    for i in range(3):
        try:
            print(f"\n시도 #{i+1} - ", end="")
            start = time.time()
            response = model.generate_content("Say 'OK'")
            elapsed = time.time() - start
            print(f"성공! ({elapsed:.2f}초)")
            print(f"  응답: {response.text[:50]}")
        except Exception as e:
            print(f"실패!")
            print(f"  오류: {str(e)[:100]}")
            if "429" in str(e):
                print("  ⚠️ 할당량 초과!")
                break
        
        time.sleep(5)  # 5초 대기
    
    print()
    print("=" * 50)
    print("테스트 완료")
    print("=" * 50)
    
except Exception as e:
    print(f"❌ API 키 오류: {e}")
    print()
    print("가능한 원인:")
    print("1. 잘못된 API 키")
    print("2. 만료된 API 키")
    print("3. 네트워크 문제")
