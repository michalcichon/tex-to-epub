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
    We want to remove such <div> tags and <p><span>2</span></p> lines.
    """
    # Remove <div class="multicols">
    html_content = html_content.replace('<div class="multicols">', '')
    # Remove </div>
    html_content = html_content.replace('</div>', '')
    # Remove lines like <p><span>2</span></p>
    html_content = re.sub(r'<p><span>\d+</span></p>', '', html_content)
    return html_content

def compress_image_to_jpeg(src_path, quality=60, dpi=150):
    """
    Converts any image (PDF, PNG, JPG, etc.) to a .jpg file with a given quality (e.g. 60).
    - For PDFs: takes only the first page ([0]) and uses -density <dpi>.
    - For other formats (PNG/JPG/etc.): simply re-encodes at the given quality.
    Returns the path to the resulting .jpg file or None if an error occurs.
    
    Note: Converting PNG→JPG will remove alpha transparency.
    """
    # We'll put the resulting .jpg in the same folder, changing only the extension.
    jpg_path = src_path.with_suffix(".jpg")

    # Build the ImageMagick command
    # - If PDF, we add "[0]" to convert only first page
    if src_path.suffix.lower() == ".pdf":
        command = [
            "magick",
            "-density", str(dpi),
            f"{src_path}[0]",
            "-quality", str(quality),
            str(jpg_path)
        ]
    else:
        # For PNG/JPG/etc., just convert and compress
        # Optionally, you could set -resize or other params if you want smaller dimensions.
        command = [
            "magick",
            str(src_path),
            "-quality", str(quality),
            str(jpg_path)
        ]

    try:
        subprocess.run(command, check=True)
        return jpg_path
    except Exception as e:
        print(f"Error compressing {src_path} to JPEG: {e}")
        return None

def replace_image_references_in_html(html_content, media_dir, tex_dir):
    """
    Replaces Pandoc's <span class="image placeholder" data-original-image-src="..."> 
    with <img src="...">. 
    Additionally, compresses ALL images (PDF, PNG, JPG, etc.) to a .jpg with ~quality=60.
    The final .jpg is placed in media_dir, so add_media_to_epub() can package it.
    """

    pattern = re.compile(
        r'<span\s+class="image placeholder"([^>]*)data-original-image-src="([^"]+)"([^>]*)>(.*?)</span>',
        flags=re.DOTALL
    )

    def replace_placeholder(match):
        whole_span = match.group(0)
        image_file = match.group(2)

        # Try media_dir first (maybe Pandoc already extracted it there)
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

        # Now compress/convert to .jpg (with quality ~60)
        compressed_jpg = compress_image_to_jpeg(final_image_path, quality=60)
        if not compressed_jpg or not compressed_jpg.is_file():
            print(f"Warning: Failed to compress '{image_file}' to JPG.")
            return whole_span

        # Ensure the final .jpg is in media_dir
        if media_dir:
            target_path = Path(media_dir) / compressed_jpg.name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path != compressed_jpg:
                try:
                    copyfile(compressed_jpg, target_path)
                    compressed_jpg = target_path
                except Exception as e:
                    print(f"Error copying '{compressed_jpg}' to '{target_path}': {e}")
                    return whole_span

        return f'<img src="{compressed_jpg.name}" alt="image">'

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
    Scans `media_dir` and adds recognized image files to the ePub.
    This ensures they are included in the final output.epub package.
    """
    if not media_dir or not Path(media_dir).is_dir():
        return

    for media_file in Path(media_dir).glob("**/*"):
        suffix_lower = media_file.suffix.lower().strip(".")
        if suffix_lower in ["jpg", "jpeg", "png", "gif", "svg"]:
            with open(media_file, "rb") as f:
                epub_item = epub.EpubItem(
                    uid=media_file.name,
                    file_name=media_file.name,
                    media_type=f"image/{suffix_lower}",
                    content=f.read()
                )
                book.add_item(epub_item)

def convert_tex_to_epub(config_path):
    """
    Reads a JSON config and converts multiple .tex files into one .epub.
    - Possibly uses a cover image,
    - Ignores {multicols} environment,
    - Compresses all images to ~quality=60 (PDF->JPG, PNG->JPG, etc.),
    - Ensures final images are placed in media_dir, then calls add_media_to_epub().
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

    # Optional debug log
    log_file = None
    if debug:
        log_file = f"{Path(config_path).stem}.log"
        with open(log_file, "w") as log:
            log.write("Debugging enabled. Starting conversion.\n")

    # Create new ePub
    book = epub.EpubBook()
    book.set_identifier("id123456")
    book.set_title("Generated ePub")
    book.set_language("en")

    # Add cover if available
    if cover_path and Path(cover_path).is_file():
        with open(cover_path, 'rb') as cover_file:
            book.set_cover("cover.jpg", cover_file.read())
    else:
        print("Warning: Cover file not found or not specified. Proceeding without a cover.")
        if debug and log_file:
            with open(log_file, "a") as log:
                log.write("Warning: Cover file not found.\n")

    # Debug directory for .html if needed
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

        # Pandoc .tex -> .html
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

        # Move the .html to debug folder if needed
        if debug and html_dir:
            debug_html_path = Path(html_dir) / Path(html_file).name
            Path(html_file).rename(debug_html_path)
            html_file = debug_html_path

        # Read the generated HTML
        with open(html_file, 'r', encoding='utf-8') as file:
            html_content = file.read()

        # Remove traces of {multicols}
        html_content = remove_multicols_html(html_content)

        # Replace placeholders with <img>, compress images to ~60
        tex_dir = Path(tex_file).parent
        html_content = replace_image_references_in_html(html_content, media_dir, tex_dir)

        # Create ePub chapter
        chapter = epub.EpubHtml(
            title=f"Chapter {index + 1}",
            file_name=f"chapter_{index + 1}.xhtml",
            lang="en"
        )
        chapter.content = html_content
        book.add_item(chapter)
        book.spine.append(chapter)

        # Finally add images from media_dir (the newly-compressed .jpg files)
        if extract_media:
            add_media_to_epub(media_dir, book)

    # Navigation
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Write final ePub
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
