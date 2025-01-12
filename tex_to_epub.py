import json
import os
from pathlib import Path
from ebooklib import epub
import subprocess
import re
from shutil import copyfile

def copy_image_to_html_dir(image_path, html_dir):
    """Copies an image to the HTML directory and returns the new relative path."""
    html_image_path = Path(html_dir) / Path(image_path).name
    try:
        copyfile(image_path, html_image_path)
        return html_image_path
    except Exception as e:
        print(f"Error copying image {image_path} to {html_image_path}: {e}")
        return None

def replace_image_references_in_html(html_content, media_dir, tex_dir, html_dir):
    """Replaces LaTeX image references in HTML with proper <img> tags."""
    def replace_match(match):
        image_file = match.group(1)

        # Check in media_dir first
        image_path = Path(media_dir) / image_file if media_dir else None
        if not image_path or not image_path.is_file():
            # Fallback to the directory containing the .tex file
            image_path = Path(tex_dir) / image_file

        if not image_path.is_file():
            print(f"Warning: Image file '{image_file}' not found in media directory or tex directory.")
            return match.group(0)  # Leave original if image file is missing

        # Copy image to HTML directory
        copied_image_path = copy_image_to_html_dir(image_path, html_dir)
        if not copied_image_path:
            return match.group(0)  # Leave original if copy fails

        # Generate proper <img> tag
        return f'<img src="{copied_image_path.name}" alt="Image">'

    # Replace placeholders in HTML
    image_pattern = re.compile(r'data-original-image-src="(.*?)"')
    return image_pattern.sub(replace_match, html_content)

def convert_tex_to_html(tex_file, template=None, extract_media=False, debug=False, log_file=None):
    """Converts a LaTeX file to HTML using pandoc, with optional template and media extraction support."""
    output_html = tex_file.replace(".tex", ".html")
    command = ["pandoc", tex_file, "-o", output_html]

    # Add optional template
    if template:
        command.extend(["--template", template])

    # Add media extraction option
    media_dir = None
    if extract_media:
        media_dir = tex_file.replace(".tex", "_media")
        command.extend(["--extract-media", media_dir])

    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE if debug else subprocess.DEVNULL, stderr=subprocess.PIPE if debug else subprocess.DEVNULL)
        if debug and log_file:
            with open(log_file, "a") as log:
                log.write(f"Successfully converted {tex_file} to HTML.\n")
    except subprocess.CalledProcessError as e:
        if debug and log_file:
            with open(log_file, "a") as log:
                log.write(f"Error converting {tex_file} to HTML: {e}\n")
        return None, None

    return output_html, media_dir

def add_media_to_epub(media_dir, book):
    """Adds media files from the specified directory to the ePub book."""
    if not media_dir or not Path(media_dir).is_dir():
        return

    for media_file in Path(media_dir).glob("**/*"):
        with open(media_file, "rb") as file:
            epub_item = epub.EpubItem(
                uid=media_file.name,
                file_name=str(media_file.name),
                media_type=f"image/{media_file.suffix[1:]}",
                content=file.read()
            )
            book.add_item(epub_item)

def convert_tex_to_epub(config_path):
    # Load configuration
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    cover_path = config.get("cover")
    materials = config.get("materials", [])
    template = config.get("template")
    extract_media = config.get("extractMedia", False)
    debug = config.get("debug", False)

    if not materials:
        raise ValueError("No materials specified in the configuration file.")

    # Prepare logging if debug is enabled
    log_file = None
    if debug:
        log_file = f"{Path(config_path).stem}.log"
        with open(log_file, "w") as log:
            log.write("Debugging enabled. Starting conversion.\n")

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
        if debug and log_file:
            with open(log_file, "a") as log:
                log.write("Warning: Cover file not found.\n")

    # Convert and add materials
    html_dir = None
    if debug:
        html_dir = f"{Path(config_path).stem}-html"
        os.makedirs(html_dir, exist_ok=True)

    for index, tex_file in enumerate(materials):
        if not Path(tex_file).is_file():
            print(f"Warning: File '{tex_file}' not found. Skipping.")
            if debug and log_file:
                with open(log_file, "a") as log:
                    log.write(f"Warning: File '{tex_file}' not found. Skipping.\n")
            continue

        # Convert LaTeX to HTML
        html_file, media_dir = convert_tex_to_html(tex_file, template=template, extract_media=extract_media, debug=debug, log_file=log_file)
        if not html_file or not Path(html_file).is_file():
            print(f"Warning: Failed to convert '{tex_file}' to HTML. Skipping.")
            if debug and log_file:
                with open(log_file, "a") as log:
                    log.write(f"Warning: Failed to convert '{tex_file}' to HTML.\n")
            continue

        if debug:
            debug_html_path = Path(html_dir) / Path(html_file).name
            Path(html_file).rename(debug_html_path)
            html_file = debug_html_path

        with open(html_file, 'r', encoding='utf-8') as file:
            html_content = file.read()

        # Replace image placeholders in HTML
        tex_dir = Path(tex_file).parent
        html_content = replace_image_references_in_html(html_content, media_dir, tex_dir, html_dir)

        chapter = epub.EpubHtml(
            title=f"Chapter {index + 1}",
            file_name=f"chapter_{index + 1}.xhtml",
            lang="en"
        )
        chapter.content = html_content
        book.add_item(chapter)

        # Add media files to ePub
        if extract_media:
            add_media_to_epub(media_dir, book)

        # Add to book spine
        book.spine.append(chapter)

    # Add default navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Write ePub file
    output_file = "output.epub"
    epub.write_epub(output_file, book)
    print(f"ePub file '{output_file}' has been successfully generated.")
    if debug and log_file:
        with open(log_file, "a") as log:
            log.write(f"ePub file '{output_file}' successfully generated.\n")

if __name__ == "__main__":
    config_path = input("Enter the path to the configuration JSON file: ").strip()
    if not Path(config_path).is_file():
        print("Error: Configuration file not found.")
    else:
        try:
            convert_tex_to_epub(config_path)
        except Exception as e:
            print(f"An error occurred: {e}")
