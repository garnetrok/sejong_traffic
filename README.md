# 세종시 세이프로드 AI (SafeRoad AI) 교통 관제 시스템

세종시 교통사고 데이터를 지도·차트로 보여 주고, 머신러닝으로 법정동별 다음 분기 사고 위험을 예측하는 관제 대시보드입니다.
Flask 서버 하나가 대시보드 화면, 데이터 API, ML 학습을 모두 처리합니다.

```
브라우저 ──▶ [Flask 서버 (Render)] ──▶ [Supabase DB]
              /           대시보드 화면 (web/)
              /api/...    데이터 조회·업로드·상태 변경·ML 재학습
              /recompute  ML 재학습 (외부 호출용)
```

## 폴더 구조

| 경로 | 내용 |
|---|---|
| `app.py` | Flask 서버 — 화면(`/`), API(`/api/<함수명>`), `/health`, `/recompute` |
| `dashboard_api.py` | 화면이 부르는 서버 함수 (데이터 조회, 엑셀 업서트, 조치 상태 변경, ML 점수, Gemini) |
| `web/` | 대시보드 화면 (`index.html`, `script.html`, `style.html`, `server-bridge.js`) |
| `fetch_data.py` | Supabase에서 1,000행씩 나눠 전체 데이터 조회 |
| `prepare_features.py` | 법정동·연·월 단위 특성 생성 |
| `train_model.py` | train / validation / test 연도 분할 평가 |
| `predict_next_quarter.py` | 다음 분기 3개월 예측 (단독 실행용) |
| `save_predictions.py` | 평가 → 재학습 → 예측 → `ml_model_eval`, `ml_safety_scores` 저장 |
| `gunicorn.conf.py` | 서버 응답 제한 시간 180초 (ML 재학습용) |
| `supabase/schema.sql` | 테이블 참고 스키마 (새 DB를 만들 때만) |

## 환경 변수

| 이름 | 필수 | 내용 |
|---|---|---|
| `SUPABASE_URL` | ✅ | `https://<project-ref>.supabase.co` |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service_role 키 |
| `DASHBOARD_PASSWORD` | 권장 | 설정하면 접속할 때 비밀번호를 물어봄 (아이디 칸은 아무거나) |
| `GEMINI_API_KEY` | 선택 | Gemini 리포트용 |

키는 코드에 넣지 않습니다. 로컬은 `.env`(깃에 안 올라감), Render는 Environment 메뉴에 넣습니다.

## Render에서 실행 (깃헙에 올리면 자동 배포)

이미 Render 서비스가 이 저장소에 연결되어 있다면 **깃헙에 푸시하는 것만으로 자동 배포**됩니다.

처음 만드는 경우: Render > New > Web Service > 이 저장소 선택

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Environment: 위 환경 변수 입력

배포가 끝나면 `https://<서비스이름>.onrender.com` 으로 접속합니다.
무료 플랜은 잠들어 있다가 첫 접속에 깨어나므로 30~50초 걸릴 수 있습니다.

## 내 PC에서 실행 (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env                      # Supabase URL과 키 입력 후 저장
.venv\Scripts\python.exe app.py   # 브라우저에서 http://localhost:5000
```

## 데이터 흐름 메모

- 화면 코드는 원래 Google Apps Script용이라 `google.script.run.함수명()` 으로 서버를 부릅니다. `web/server-bridge.js`가 이 호출을 `/api/함수명` 요청으로 바꿔 주므로 화면 코드는 수정하지 않았습니다.
- 엑셀 업로드는 `incident_no`(사고번호) 기준 업서트라서 같은 파일을 다시 올려도 중복되지 않습니다 (`incident_no`에 UNIQUE 제약 필요).
- ML 서버는 법정동별 **예상 사고 건수**를 저장하고, 화면에는 동네끼리 비교한 **안전 점수**(예상 사고가 가장 적은 동 100점, 가장 많은 동 40점)로 바꿔 보여 줍니다.
- 엑셀 업로드로 들어오는 행에는 `date`, `region`, `accident_type`, `occrrnc_cnt`, `weather`만 채워지고, ML이 쓰는 `legal_dong_name`, `occurred_year`, `occurred_month` 등은 비어 있습니다.
- `web/style.html`은 원본 Apps Script에서 CSS가 스크립트로 덮어써져 유실되어, 2026-07-19 `test.html`의 CSS에 이후 추가된 요소 스타일을 보충해 복원한 것입니다.
