import json
import os
from pathlib import Path
from ebooklib import epub
import subprocess
import re
from shutil import copyfile

def remove_multicols_html(html_content):
    """
    Removes extra HTML fragments left by {multicols} environment in LaTeX.
    For example, Pandoc might produce <div class="multicols"><p><span>2</span></p> ... </div>.
    We want to remove such <div> tags and the <p><span>2</span></p> lines.
    """
    # Remove <div class="multicols">
    html_content = html_content.replace('<div class="multicols">', '')
    # Remove </div>
    html_content = html_content.replace('</div>', '')
    # Remove lines like <p><span>2</span></p> (could be 2, 3, ...)
    html_content = re.sub(r'<p><span>\d+</span></p>', '', html_content)
    return html_content

def convert_pdf_to_jpg(pdf_path, dpi=150, quality=90):
    """
    Converts the first page of a PDF file to JPG using ImageMagick.
    In ImageMagick 7, the recommended command is 'magick'.
    Returns the path to the generated JPG or None if it fails.
    """
    jpg_path = pdf_path.with_suffix(".jpg")
    command = [
        "magick",                # instead of "convert" for IMv7
        "-density", str(dpi),
        str(pdf_path) + "[0]",   # [0] = first page only
        "-quality", str(quality),
        str(jpg_path)
    ]
    try:
        subprocess.run(command, check=True)
        return jpg_path
    except Exception as e:
        print(f"Error converting {pdf_path} to JPG: {e}")
        return None

def replace_image_references_in_html(html_content, media_dir, tex_dir):
    """
    Replaces Pandoc's image placeholders <span class="image placeholder" data-original-image-src="...">
    with <img> tags. If the file is PDF, convert to JPG. 
    The final images are placed in `media_dir`, so they can be included in the ePub.
    """
    pattern = re.compile(
        r'<span\s+class="image placeholder"([^>]*)data-original-image-src="([^"]+)"([^>]*)>(.*?)</span>',
        flags=re.DOTALL
    )

    def replace_placeholder(match):
        whole_span = match.group(0)
        image_file = match.group(2)

        # Try to find the file in media_dir first (if Pandoc already extracted it)
        final_image_path = None
        if media_dir:
            candidate = Path(media_dir) / image_file
            if candidate.is_file():
                final_image_path = candidate

        # If not found, check the .tex file directory
        if not final_image_path:
            candidate = Path(tex_dir) / image_file
            if candidate.is_file():
                final_image_path = candidate

        if not final_image_path or not final_image_path.is_file():
            print(f"Warning: Image file '{image_file}' not found.")
            return whole_span

        # If the file is PDF, convert to JPG
        if final_image_path.suffix.lower() == ".pdf":
            converted_jpg = convert_pdf_to_jpg(final_image_path)
            if not converted_jpg or not converted_jpg.is_file():
                print(f"Warning: Failed to convert '{image_file}' to JPG.")
                return whole_span
            final_image_path = converted_jpg

        # Ensure the final image is in media_dir
        if media_dir:
            target_path = Path(media_dir) / final_image_path.name

            # Make sure the target subdirectory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # If the file isn't already in that exact location, copy it
            if target_path != final_image_path:
                try:
                    copyfile(final_image_path, target_path)
                    final_image_path = target_path
                except Exception as e:
                    print(f"Error copying image '{final_image_path}' to '{target_path}': {e}")
                    return whole_span

        # Return <img src="ImageName.jpg">
        return f'<img src="{final_image_path.name}" alt="image">'

    new_html = pattern.sub(replace_placeholder, html_content)
    return new_html

def convert_tex_to_html(tex_file, template=None, extract_media=False, debug=False, log_file=None):
    """
    Converts a .tex file to HTML via Pandoc.
    If extract_media=True, uses --extract-media to place images into a separate folder.
    """
    output_html = tex_file.replace(".tex", ".html")
    command = ["pandoc", tex_file, "-o", output_html]

    if template:
        command.extend(["--template", template])

    media_dir = None
    if extract_media:
        # Pandoc will place images here
        media_dir = tex_file.replace(".tex", "_media")
        command.extend(["--extract-media", media_dir])

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE if debug else subprocess.DEVNULL,
            stderr=subprocess.PIPE if debug else subprocess.DEVNULL
        )
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
    """
    Scans `media_dir` and adds recognized image files to the ePub
    (jpg, jpeg, png, gif, svg).
    """
    if not media_dir or not Path(media_dir).is_dir():
        return

    for media_file in Path(media_dir).glob("**/*"):
        suffix_lower = media_file.suffix.lower().strip(".")
        if suffix_lower in ["jpg", "jpeg", "png", "gif", "svg"]:
            with open(media_file, "rb") as f:
                epub_item = epub.EpubItem(
                    uid=media_file.name,
                    file_name=media_file.name,  # or e.g. "images/filename"
                    media_type=f"image/{suffix_lower}",
                    content=f.read()
                )
                book.add_item(epub_item)

def convert_tex_to_epub(config_path):
    """
    Reads a JSON config and converts multiple .tex files into one .epub.
    - Possibly uses a cover image,
    - Uses remove_multicols_html() to remove {multicols} artifacts,
    - Replaces image placeholders with <img> tags (and converts PDFs to JPG),
    - Ensures all images end up in media_dir, which is then added to ePub.
    """
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    cover_path = config.get("cover")
    materials = config.get("materials", [])
    template = config.get("template")
    extract_media = config.get("extractMedia", False)
    debug = config.get("debug", False)

    if not materials:
        raise ValueError("No materials specified in the configuration file.")

    # Prepare debug logging if needed
    log_file = None
    if debug:
        log_file = f"{Path(config_path).stem}.log"
        with open(log_file, "w") as log:
            log.write("Debugging enabled. Starting conversion.\n")

    # Create a new ePub book
    book = epub.EpubBook()
    book.set_identifier("id123456")
    book.set_title("Generated ePub")
    book.set_language("en")

    # Add cover if exists
    if cover_path and Path(cover_path).is_file():
        with open(cover_path, 'rb') as cover_file:
            book.set_cover("cover.jpg", cover_file.read())
    else:
        print("Warning: Cover file not found or not specified. Proceeding without a cover.")
        if debug and log_file:
            with open(log_file, "a") as log:
                log.write("Warning: Cover file not found.\n")

    # Optional directory to store debug .html
    html_dir = None
    if debug:
        html_dir = f"{Path(config_path).stem}-html"
        os.makedirs(html_dir, exist_ok=True)

    # Process each .tex file
    for index, tex_file in enumerate(materials):
        if not Path(tex_file).is_file():
            print(f"Warning: File '{tex_file}' not found. Skipping.")
            if debug and log_file:
                with open(log_file, "a") as log:
                    log.write(f"Warning: File '{tex_file}' not found. Skipping.\n")
            continue

        # Convert .tex -> .html with Pandoc
        html_file, media_dir = convert_tex_to_html(
            tex_file,
            template=template,
            extract_media=extract_media,
            debug=debug,
            log_file=log_file
        )
        if not html_file or not Path(html_file).is_file():
            print(f"Warning: Failed to convert '{tex_file}' to HTML. Skipping.")
            if debug and log_file:
                with open(log_file, "a") as log:
                    log.write(f"Warning: Failed to convert '{tex_file}' to HTML.\n")
            continue

        # Move the generated .html to the debug folder if needed
        if debug and html_dir:
            debug_html_path = Path(html_dir) / Path(html_file).name
            Path(html_file).rename(debug_html_path)
            html_file = debug_html_path

        # Read the generated HTML
        with open(html_file, 'r', encoding='utf-8') as file:
            html_content = file.read()

        # Remove multicols markup
        html_content = remove_multicols_html(html_content)

        # Replace placeholders with <img> and handle PDF->JPG
        tex_dir = Path(tex_file).parent
        html_content = replace_image_references_in_html(html_content, media_dir, tex_dir)

        # Create an ePub chapter
        chapter = epub.EpubHtml(
            title=f"Chapter {index + 1}",
            file_name=f"chapter_{index + 1}.xhtml",
            lang="en"
        )
        chapter.content = html_content
        book.add_item(chapter)

        # Add the chapter to the spine
        book.spine.append(chapter)

        # Finally, add images from media_dir to the ePub
        if extract_media:
            add_media_to_epub(media_dir, book)

    # Add default navigation
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Write the final ePub file
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
