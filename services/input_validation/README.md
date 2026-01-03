# Set Up Taxodactyl Input Validation Program

This program is used to provide a web page to users to validate Taxodactyl input. Related code is p0_validation.py. 

## Prerequisites

- Python 3.10+
- Node.js 18+ (includes npm)

## Set Up
Clone the whole GitHub repository:

```
git clone https://github.com/qcif/taxodactyl.git
```

Create a virtual environment for back end
```
py -3 -m venv venv  
### Windows only
venv/Scripts/activate  
python -m pip install -r requirements.txt
``` 


## Run Back end

Use below command in virtual environment to run back end:
```bash
uvicorn main:app --reload --port 8000
```

## Run front end

Use below command to run front end:
```
npm install
npm run dev
```