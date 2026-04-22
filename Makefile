build:
	docker build --platform linux/amd64 -t chordlens-be .

dev:
	docker run --rm -p 8000:8000 --env-file .env chordlens-be
