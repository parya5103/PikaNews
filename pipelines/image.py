import os
import hashlib
from io import BytesIO
from typing import Dict, Any, Optional
from PIL import Image
import imagehash
from scrapers.engine import ScraperEngine
import structlog

logger = structlog.get_logger(__name__)

class ImagePipeline:
    def __init__(self, config: Dict[str, Any], engine: ScraperEngine):
        self.config = config
        self.engine = engine
        self.storage_dir = config.get("image_storage", {}).get("dir", "./storage/images")
        self.sizes = config.get("image_storage", {}).get("sizes", {
            "thumbnail": [150, 150],
            "medium": [600, 400],
            "full": [1200, 800]
        })
        os.makedirs(self.storage_dir, exist_ok=True)

    def _generate_p_hash(self, img: Image.Image) -> str:
        """Generate perceptual difference hash (dhash) for image."""
        try:
            return str(imagehash.dhash(img))
        except Exception as e:
            logger.warn("Perceptual hash generation failed", error=str(e))
            return ""

    async def process_image(self, image_url: str, source_name: str) -> Dict[str, Any]:
        """Download, resize into variants, and calculate perceptual hash for image."""
        result = {
            "image_phash": None,
            "local_paths": {}
        }
        
        if not image_url:
            return result

        try:
            logger.info("Downloading featured image", url=image_url, source=source_name)
            img_bytes = await self.engine.fetch(source_name, image_url, response_format="bytes")
            if not img_bytes:
                logger.warn("Failed to download image bytes", url=image_url)
                return result

            # Open image with Pillow
            img = Image.open(BytesIO(img_bytes))
            # Normalize to RGB (handles PNG/RGBA or WebP properly)
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Calculate pHash
            phash = self._generate_p_hash(img)
            result["image_phash"] = phash

            # Create source directory structure: storage/images/<source>/<hash>/
            url_hash = hashlib.sha256(image_url.encode()).hexdigest()[:16]
            dest_folder = os.path.join(self.storage_dir, source_name, url_hash)
            os.makedirs(dest_folder, exist_ok=True)

            # Generate and save resized versions
            for size_name, dimensions in self.sizes.items():
                target_w, target_h = dimensions
                
                # Copy and resize keeping aspect ratio
                variant = img.copy()
                variant.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
                
                # Construct filename and save
                filename = f"{size_name}.jpg"
                filepath = os.path.join(dest_folder, filename)
                variant.save(filepath, "JPEG", quality=85)
                
                # Save relative path for database reference
                result["local_paths"][size_name] = filepath.replace("\\", "/")

            logger.info("Processed image successfully", source=source_name, phash=phash)

        except Exception as e:
            logger.error("Failed to process image", url=image_url, error=str(e))

        return result
