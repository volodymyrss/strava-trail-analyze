IMAGE=volodymyrsavchenko/trails:$(shell git describe --always --tags)

build:
	docker build -f Dockerfile.app . -t $(IMAGE)

run: build
	docker run \
	    --user 1000:1000 \
	    -v $(PWD)/data:/home/app/ \
	    -v $(PWD)/client.yaml:/client.yaml:ro \
	    -e OAUTH_REDIRECT=http://trail.volodymyrsavchenko.com:8000/exchange_token \
	    -e FLASK_SECRET_KEY=$(shell openssl rand -base64 32) \
	    -it -p8000:8000 $(IMAGE)

push: build
	docker push $(IMAGE)

listen:
	FLASK_TEMPLATES=$(shell pwd)/app/templates \
	FLASK_STATIC=$(shell pwd)/app/static \
	FLASK_SECRET_KEY=$(shell openssl rand -base64 32) \
			FLASK_APP=trailsapp:app flask run -h 127.0.0.1 -p 8000 --debugger 
			#gunicorn trailsapp:app -b 0.0.0.0:8000 --log-level debug

up: push
	helm upgrade --install trails chart --set image.tag=$(shell git describe --always --tags)

cert-manager:
	kubectl apply --validate=false -f https://github.com/jetstack/cert-manager/releases/download/v1.4.2/cert-manager.yaml
	#kubectl apply --validate=false -f https://github.com/jetstack/cert-manager/releases/download/v0.16.1/cert-manager.yaml

