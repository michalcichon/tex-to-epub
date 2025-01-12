import json
import os
from pathlib import Path
from ebooklib import epub
import subprocess
import re

def convert_tex_to_html(tex_file, template=None):
    """Converts a LaTeX file to HTML using pandoc, with optional template support."""
    output_html = tex_file.replace(".tex", ".html")
    command = ["pandoc", tex_file, "-o", output_html]
    if template:
        command.extend(["--template", template])
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error converting {tex_file} to HTML: {e}")
        return None
    return output_html

def convert_tex_to_epub(config_path):
    # Load configuration
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    cover_path = config.get("cover")
    materials = config.get("materials", [])
    template = config.get("template")

    if not materials:
        raise ValueError("No materials specified in the configuration file.")

    # Create ePub book
    book = epub.EpubBook()
    book.set_identifier("id123456")
    book.set_title("Generated ePub")
    book.set_language("en")

    # Add cover
    if cover_path and Path(cover_path).is_file():
        with open(cover_path, 'rb') as cover_file:
            book.set_cover("cover.jpg", cover_file.read())
    else:
        print("Warning: Cover file not found or not specified. Proceeding without a cover.")

    # Convert and add materials
    for index, tex_file in enumerate(materials):
        if not Path(tex_file).is_file():
            print(f"Warning: File '{tex_file}' not found. Skipping.")
            continue

        # Convert LaTeX to HTML
        html_file = convert_tex_to_html(tex_file, template=template)
        if not html_file or not Path(html_file).is_file():
            print(f"Warning: Failed to convert '{tex_file}' to HTML. Skipping.")
            continue

        with open(html_file, 'r', encoding='utf-8') as file:
            html_content = file.read()

        chapter = epub.EpubHtml(
            title=f"Chapter {index + 1}",
            file_name=f"chapter_{index + 1}.xhtml",
            lang="en"
        )
        chapter.content = html_content
        book.add_item(chapter)

        # Add to book spine
        book.spine.append(chapter)

        # Cleanup temporary HTML file
        os.remove(html_file)

    # Add default navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Write ePub file
    output_file = "output.epub"
    epub.write_epub(output_file, book)
    print(f"ePub file '{output_file}' has been successfully generated.")

if __name__ == "__main__":
    config_path = input("Enter the path to the configuration JSON file: ").strip()
    if not Path(config_path).is_file():
        print("Error: Configuration file not found.")
    else:
        try:
            convert_tex_to_epub(config_path)
        except Exception as e:
            print(f"An error occurred: {e}")
