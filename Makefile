IMAGE=volodymyrsavchenko/trails:$(shell git describe --always --tags)

build:
	docker build . -t $(IMAGE)

run:
	docker run $(IMAGE)

listen:
	gunicorn trailsapp:app -b 0.0.0.0:8000 --log-level debug
