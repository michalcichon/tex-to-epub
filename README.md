# tex-to-epub Converter

This script converts `.tex` files to an ePub format using `pandoc` for LaTeX-to-HTML conversion and the `ebooklib` library to generate ePub files. It supports configuring the cover image, ordering the materials, using a custom template, optionally extracting media files (e.g., images), and generating debug logs. Additionally, it handles the conversion of PDF files to images (e.g., JPEG) for embedding in the ePub.

## Dependencies

Ensure you have the following dependencies installed:

### Python Libraries

Install required Python libraries using pip:

```bash
pip install ebooklib pdf2image
```

### External Tools

1. **pandoc**: Used for converting LaTeX to HTML.
   - Install `pandoc`:
     - **Linux (Debian/Ubuntu):**
       ```bash
       sudo apt install pandoc
       ```
     - **macOS:**
       ```bash
       brew install pandoc
       ```
     - **Windows:**
       ```bash
       choco install pandoc
       ```

2. **Poppler**: Required by `pdf2image` to process PDF files.
   - **macOS:**
     ```bash
     brew install poppler
     ```
   - **Linux (Debian/Ubuntu):**
     ```bash
     sudo apt install poppler-utils
     ```
   - **Windows:**
     1. Download Poppler for Windows from [here](https://github.com/oschwartz10612/poppler-windows/releases/).
     2. Extract the archive and add the `bin` folder to your system's PATH.

### Verifying Installation

To confirm that `pdf2image` and Poppler are installed correctly, you can run:

```python
from pdf2image import convert_from_path
images = convert_from_path("example.pdf")
print(f"Converted {len(images)} pages from PDF to images.")
```

## Usage

### Prepare the Configuration File

The script uses a JSON configuration file to specify the cover image, LaTeX files to include, optional template, media extraction, and debug mode. The configuration file should follow this structure:

```json
{
    "cover": "path/to/cover.jpg",
    "materials": [
        "path/to/file1.tex",
        "path/to/file2.tex"
    ],
    "template": "path/to/template.html",
    "extractMedia": true,
    "debug": true
}
```

- **`cover`**: Path to the cover image file (e.g., `.jpg` or `.png`).
- **`materials`**: List of `.tex` files to include in the ePub, in the desired order.
- **`template`**: Path to a custom HTML template for `pandoc` (optional).
- **`extractMedia`**: Boolean flag to enable or disable extraction of media files (e.g., images). When enabled, `pandoc` will extract media files and the script will embed them into the ePub.
- **`debug`**: Boolean flag to enable or disable debug mode. When enabled, the script generates:
  - A log file named `<config-name>.log` with detailed conversion logs.
  - A directory named `<config-name>-html` containing intermediate HTML files.

### Run the Script

1. Save the script as `tex_to_epub.py`.
2. Prepare a valid JSON configuration file, e.g., `config.json`.
3. Run the script and provide the path to the configuration file when prompted:

```bash
python tex_to_epub.py
```

Example input when prompted:

```plaintext
Enter the path to the configuration JSON file: config.json
```

### Output

The script generates:

- An ePub file named `output.epub` in the current working directory.
- If `debug` is enabled:
  - Log file: `<config-name>.log`.
  - HTML files: Directory `<config-name>-html` containing intermediate HTML files.

### Example Configuration

```json
{
    "cover": "images/cover.jpg",
    "materials": [
        "documents/chapter1.tex",
        "documents/chapter2.tex"
    ],
    "template": "templates/custom_template.html",
    "extractMedia": true,
    "debug": true
}
```

### Running the Script

```bash
python tex_to_epub.py
```

### Result

The script processes the `.tex` files, converts them to HTML using `pandoc`, and assembles them into an ePub file named `output.epub` with the specified cover, embedded images, and optional debug outputs.

## Troubleshooting

1. **Error: `pandoc` not found**:
   - Ensure `pandoc` is installed and added to your system's PATH.

2. **Error: `ModuleNotFoundError: No module named 'pdf2image'`**:
   - Install the library using `pip install pdf2image`.
   - Ensure Poppler is installed and accessible (see dependencies).

3. **Warnings about missing files**:
   - Double-check the paths in `config.json` and ensure the files exist.

4. **Issues with LaTeX syntax**:
   - Ensure the `.tex` files are valid and supported by `pandoc`.

5. **Images not appearing in ePub**:
   - Ensure `extractMedia` is set to `true` in the configuration file.
   - Verify that the image paths in the `.tex` files are correct and the files exist.

6. **Debugging output**:
   - Check the log file (`<config-name>.log`) for detailed information on the conversion process.

For further assistance, feel free to contact the maintainer or consult the documentation for `pandoc`, `ebooklib`, and `pdf2image`.

