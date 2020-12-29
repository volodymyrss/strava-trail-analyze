IMAGE=volodymyrsavchenko/trails:$(shell git describe --always --tags)

build:
	docker build . -t $(IMAGE)

run: build
	docker run -it -p8000:8000 $(IMAGE)

push: build
	docker push $(IMAGE)

listen:
	gunicorn trailsapp:app -b 0.0.0.0:8000 --log-level debug

up: push
	helm upgrade --install trails chart --set image.tag=$(git describe --always --tags)
