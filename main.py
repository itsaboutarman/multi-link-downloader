import asyncio
import aiohttp
import aiofiles
import os

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MAX_CONCURRENT_DOWNLOADS = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/115.0.0.0 Safari/537.36"
}


async def download_file(session, url):
    """
    Downloads a single file from a URL, with resumable download support.
    """
    # Extract filename from URL
    filename = url.split("filename=")[-1]
    filename = filename.replace("%20", " ")
    filepath = os.path.join(DOWNLOAD_DIR, filename)

    # --- NEW: Logic for resumable download ---
    start_byte = 0
    mode = 'wb'  # Default mode is 'write binary' (new download)
    resume_headers = headers.copy()

    # Check if a partial file exists
    if os.path.exists(filepath):
        start_byte = os.path.getsize(filepath)
        if start_byte > 0:
            # Set the 'Range' header to resume the download from the last byte
            resume_headers['Range'] = f'bytes={start_byte}-'
            print(
                f"✅ Resuming download of: {filename} from byte {start_byte}...")
        else:
            print(f"Starting new download of: {filename}")
    else:
        print(f"Starting new download of: {filename}")

    try:
        async with semaphore:
            async with session.get(url, headers=resume_headers) as resp:
                if resp.status == 206:  # 206 Partial Content: Server supports resuming
                    mode = 'ab'  # Change mode to 'append binary'
                    total_size = resp.headers.get('Content-Length')
                    # Update total size to include the bytes already downloaded
                    if total_size:
                        total_size = int(total_size) + start_byte
                    print(f"  > Server confirmed resume. Appending to file...")
                elif resp.status == 200:  # 200 OK: Server doesn't support resuming from this point, restart
                    mode = 'wb'  # Start from scratch
                    if start_byte > 0:
                        print(
                            "  > Server does not support resuming. Restarting download from scratch.")
                    total_size = resp.headers.get('Content-Length')
                    start_byte = 0  # Reset downloaded size
                else:
                    print(f"❌ Failed to download {url}. Status: {resp.status}")
                    return  # Exit the function on failure
                # --- END NEW CHECK ---

                # Write the content to the file
                downloaded_size = start_byte
                async with aiofiles.open(filepath, mode=mode) as f:
                    async for chunk in resp.content.iter_chunked(1024):
                        await f.write(chunk)
                        downloaded_size += len(chunk)
                        # --- NEW: Simple progress indicator ---
                        if total_size:
                            percent = (downloaded_size / int(total_size)) * 100
                            print(
                                f"  > {filename}: {percent:.2f}% downloaded", end='\r')
                    print(f"\n✅ Downloaded: {filename}")

    except Exception as e:
        print(f"\n❌ Error downloading {url}: {e}")


async def main():
    async with aiohttp.ClientSession(headers=headers) as session:
        # Open links.txt and create a task for each URL
        with open("links.txt", "r") as file:
            urls = [line.strip() for line in file if line.strip()]

        # Create a list of all download tasks
        tasks = [download_file(session, url) for url in urls]

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Run the main asynchronous function
    asyncio.run(main())
