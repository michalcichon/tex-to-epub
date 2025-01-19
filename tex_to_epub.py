import json
import os
from pathlib import Path
from ebooklib import epub
import subprocess
import re
from shutil import copyfile

def remove_multicols_html(html_content):
    """
    Removes extra HTML fragments left by the {multicols} environment in LaTeX.
    For instance, Pandoc might insert <div class="multicols"><p><span>2</span></p> ... </div>.
    We want to remove the entire <div> ... </div> and any <p><span>2</span></p> lines.
    """
    # Remove opening <div class="multicols">
    html_content = html_content.replace('<div class="multicols">', '')
    # Remove closing </div>
    html_content = html_content.replace('</div>', '')
    # Remove lines like <p><span>2</span></p> (could be 2, 3, etc.)
    html_content = re.sub(r'<p><span>\d+</span></p>', '', html_content)
    return html_content

def copy_image_to_html_dir(image_path, html_dir):
    """
    Copies an image file to the specified HTML directory and returns the new path.
    If there's an error, returns None.
    """
    html_image_path = Path(html_dir) / Path(image_path).name
    try:
        copyfile(image_path, html_image_path)
        return html_image_path
    except Exception as e:
        print(f"Error copying image {image_path} to {html_image_path}: {e}")
        return None

def convert_pdf_to_jpg(pdf_path, dpi=150, quality=90):
    """
    Converts the first page of a .pdf file to a .jpg using ImageMagick.
    Returns the path to the generated .jpg file or None if unsuccessful.
    """
    jpg_path = pdf_path.with_suffix(".jpg")
    # This command overwrites existing jpg_path if it exists
    command = [
        "convert",
        "-density", str(dpi),
        str(pdf_path) + "[0]",  # [0] means first page only
        "-quality", str(quality),
        str(jpg_path)
    ]
    try:
        subprocess.run(command, check=True)
        return jpg_path
    except Exception as e:
        print(f"Error converting {pdf_path} to JPG: {e}")
        return None

def replace_image_references_in_html(html_content, media_dir, tex_dir, html_dir):
    """
    Replaces Pandoc's image placeholders with <img> tags in the final HTML.
    Also, if the image file is a PDF, it attempts to convert it to JPEG.
    
    Pandoc often produces something like:
    
      <span class="image placeholder" data-original-image-src="file.pdf" width="10cm">image</span>
    
    We want to replace that with:
    
      <img src="file.jpg" alt="image">
    
    (if conversion is needed for PDF).
    """

    # Regex to match the entire <span> placeholder including all attributes.
    # We capture the value of data-original-image-src="...".
    pattern = re.compile(
        r'<span\s+class="image placeholder"([^>]*)data-original-image-src="([^"]+)"([^>]*)>(.*?)</span>',
        flags=re.DOTALL
    )

    def replace_placeholder(match):
        # Full matched string (the entire <span...>...</span>)
        whole_span = match.group(0)
        before_src  = match.group(1)  # attributes before data-original-image-src
        image_file  = match.group(2)  # the filename from data-original-image-src
        after_src   = match.group(3)  # attributes after data-original-image-src
        inner_text  = match.group(4)  # text inside the span (often "image")

        # Try to find the file in media_dir first, then in the .tex file directory
        image_path = None
        if media_dir:
            candidate = Path(media_dir) / image_file
            if candidate.is_file():
                image_path = candidate
        if not image_path:
            candidate = Path(tex_dir) / image_file
            if candidate.is_file():
                image_path = candidate

        if not image_path or not image_path.is_file():
            print(f"Warning: Image file '{image_file}' not found. Using placeholder.")
            return whole_span

        # Convert PDF to JPG if needed
        if image_path.suffix.lower() == ".pdf":
            new_jpg = convert_pdf_to_jpg(image_path)
            if new_jpg and new_jpg.is_file():
                image_path = new_jpg
            else:
                print(f"Warning: Failed to convert '{image_file}' to JPG.")
                return whole_span

        # If we have a debug HTML directory, copy the image there
        if html_dir:
            copied_image_path = copy_image_to_html_dir(image_path, html_dir)
            if not copied_image_path:
                return whole_span
            return f'<img src="{copied_image_path.name}" alt="image">'
        else:
            # If html_dir is not used, just reference the original name
            return f'<img src="{image_path.name}" alt="image">'

    new_html = pattern.sub(replace_placeholder, html_content)
    return new_html

def convert_tex_to_html(tex_file, template=None, extract_media=False, debug=False, log_file=None):
    """
    Converts a LaTeX (.tex) file to HTML via Pandoc.
    Optionally uses a template and extracts media resources into a separate folder.
    """
    output_html = tex_file.replace(".tex", ".html")
    command = ["pandoc", tex_file, "-o", output_html]

    # If template is specified, use it
    if template:
        command.extend(["--template", template])

    # If we want to extract media, define a media directory for Pandoc
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
    Adds image files from the specified media directory to the ePub book.
    Only certain file extensions are processed (jpg, png, etc.).
    """
    if not media_dir or not Path(media_dir).is_dir():
        return

    for media_file in Path(media_dir).glob("**/*"):
        suffix_lower = media_file.suffix.lower().strip(".")
        if suffix_lower in ["jpg", "jpeg", "png", "gif", "svg"]:
            with open(media_file, "rb") as file:
                epub_item = epub.EpubItem(
                    uid=media_file.name,
                    file_name=str(media_file.name),
                    media_type=f"image/{suffix_lower}",
                    content=file.read()
                )
                book.add_item(epub_item)

def convert_tex_to_epub(config_path):
    """
    Main function to read a configuration JSON file and convert multiple .tex files
    into a single ePub. Applies the functions above to handle images, remove multicols, etc.
    """
    # Read config
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    cover_path = config.get("cover")
    materials = config.get("materials", [])
    template = config.get("template")
    extract_media = config.get("extractMedia", False)
    debug = config.get("debug", False)

    if not materials:
        raise ValueError("No materials specified in the configuration file.")

    # Set up logging if debug is enabled
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

    # Add cover if specified and exists
    if cover_path and Path(cover_path).is_file():
        with open(cover_path, 'rb') as cover_file:
            book.set_cover("cover.jpg", cover_file.read())
    else:
        print("Warning: Cover file not found or not specified. Proceeding without a cover.")
        if debug and log_file:
            with open(log_file, "a") as log:
                log.write("Warning: Cover file not found.\n")

    # Optional directory to store debug HTML files
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

        # Convert .tex to .html using Pandoc
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

        # If debugging, move the generated HTML into the debug directory
        if debug:
            debug_html_path = Path(html_dir) / Path(html_file).name
            Path(html_file).rename(debug_html_path)
            html_file = debug_html_path

        # Read the HTML file
        with open(html_file, 'r', encoding='utf-8') as file:
            html_content = file.read()

        # Remove <div> and <span> from the {multicols} environment
        html_content = remove_multicols_html(html_content)

        # Replace image placeholders with <img> tags
        tex_dir = Path(tex_file).parent
        html_content = replace_image_references_in_html(
            html_content,
            media_dir,
            tex_dir,
            html_dir
        )

        # Create an ePub chapter
        chapter = epub.EpubHtml(
            title=f"Chapter {index + 1}",
            file_name=f"chapter_{index + 1}.xhtml",
            lang="en"
        )
        chapter.content = html_content
        book.add_item(chapter)

        # Add extracted images to the ePub if extract_media is True
        if extract_media:
            add_media_to_epub(media_dir, book)

        # Add chapter to the spine
        book.spine.append(chapter)

    # Add default navigation files
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
