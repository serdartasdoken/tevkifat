# Tevkifat

## Project Description
This project provides a tool for analyzing VAT withholding risk in invoice text. The main script, `app.py`, reads invoices, processes them to identify key phrases and patterns, and evaluates the risk of VAT withholding based on predefined keywords and groups.

## Installation
To set up the project, follow these steps:

1. Clone the repository:
   ```sh
   git clone https://github.com/serdartasdoken/tevkifat.git
   cd tevkifat
   ```

2. Install the required dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Usage
The main script, `app.py`, can be used to analyze the VAT withholding risk of invoice texts. Here is an example usage:

```python
from tevkifat import tevkifat_kontrol

fatura_metni = "Şantiyede yapılan inşaat ve tadilat işleri için mühendislik hizmeti ile beton kalıp ve yıkım işleri. Ayrıca bina tadilatı da yapıldı."
sonuc = tevkifat_kontrol(fatura_metni, detayli_rapor=True)

print(sonuc)
```

## Files
- `app.py`: Main script for analyzing VAT withholding risk.
- `anahtar_kelimeler.json`: JSON file containing keywords and key phrases used for analysis.
- `requirements.txt`: List of required Python packages.

## License
This project is licensed under the MIT License.

For more information, refer to the [repository](https://github.com/serdartasdoken/tevkifat).
