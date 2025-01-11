# tex-to-epub Converter

This script converts `.tex` files to an ePub format using `pandoc` for LaTeX-to-HTML conversion and the `ebooklib` library to generate ePub files. It supports configuring the cover image and ordering the materials via a JSON configuration file.

## Dependencies

Ensure you have the following dependencies installed:

### Python Libraries

Install required Python libraries using pip:

```bash
pip install ebooklib
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

2. Ensure `pandoc` is accessible from your system's PATH.

## Usage

### Prepare the Configuration File

The script uses a JSON configuration file to specify the cover image and LaTeX files to include. The configuration file should follow this structure:

```json
{
    "cover": "path/to/cover.jpg",
    "materials": [
        "path/to/file1.tex",
        "path/to/file2.tex"
    ]
}
```

- **`cover`**: Path to the cover image file (e.g., `.jpg` or `.png`).
- **`materials`**: List of `.tex` files to include in the ePub, in the desired order.

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

The script generates an ePub file named `output.epub` in the current working directory.

## Example

### Sample `config.json`

```json
{
    "cover": "images/cover.jpg",
    "materials": [
        "documents/chapter1.tex",
        "documents/chapter2.tex"
    ]
}
```

### Running the Script

```bash
python tex_to_epub.py
```

### Result

The script processes the `.tex` files, converts them to HTML using `pandoc`, and assembles them into an ePub file named `output.epub` with the specified cover.

## Troubleshooting

1. **Error: `pandoc` not found**:
   - Ensure `pandoc` is installed and added to your system's PATH.

2. **Warnings about missing files**:
   - Double-check the paths in `config.json` and ensure the files exist.

3. **Issues with LaTeX syntax**:
   - Ensure the `.tex` files are valid and supported by `pandoc`.

For further assistance, feel free to contact the maintainer or consult the documentation for `pandoc` and `ebooklib`.

