CHECK=\033[32m✔\033[39m
DATE=$(shell date +%I:%M%p)

server:
	python google_appengine/dev_appserver.py app

setup: requirements.txt
	virtualenv . --distribute
	rm -rf local
	. bin/activate; pip2.7 install -r requirements.txt;
	wget -qO- -O sdk.zip http://googleappengine.googlecode.com/files/google_appengine_1.8.9.zip && unzip sdk.zip && rm sdk.zip
	@echo "Setup complete ${CHECK}"

deploy: 
	python google_appengine/appcfg.py update app/ 
	@echo "Successfully deployed at ${DATE}. ${CHECK}	"

deploy-auth: 
	python google_appengine/appcfg.py --oauth2 update app/

tests:
	python app/utils/tests.py google_appengine app/blueprints/

clean: 
	rm -rf bin lib include google_appengine
	@echo "Clean ${CHECK}"

