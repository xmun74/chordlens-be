build:
	docker build --platform linux/amd64 -t chordlens-be .

dev:
	docker run --rm -p 8000:8000 --env-file .env \
		-v $(PWD)/app:/app/app \
		chordlens-be uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
