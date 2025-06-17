import os
import gc
import time
import psutil
from datetime import datetime
from pathlib import Path
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def monitor_system_resources():
    """Monitor system resources and return if safe to continue"""
    memory_percent = psutil.virtual_memory().percent
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Stop processing if memory usage is too high
    if memory_percent > 85:
        logger.warning(f"High memory usage: {memory_percent:.1f}%")
        return False
    
    logger.info(f"System: Memory {memory_percent:.1f}%, CPU {cpu_percent:.1f}%")
    return True

def process_single_file_safe(args: Tuple[str, str, str, str, str, str]) -> dict:
    """
    Memory-safe worker function for processing a single file.
    Includes explicit memory management and error handling.
    """
    (post_file_path, comments_dir, analysis_posts_dir, analysis_comments_dir, 
     ner_model, sentiment_model) = args
    
    start_time = time.time()
    process_id = os.getpid()
    initial_memory = get_memory_usage()
    
    try:
        logger.info(f"[PID {process_id}] Starting {Path(post_file_path).name}")
        
        # Import only when needed to minimize memory footprint
        import sys
        sys.path.append(os.getcwd())
        
        from data_collection.nlp_features import RedditDataEnricher
        from data_collection.location_processor import LocationProcessor
        from data_collection.person_name_mapper import WikipediaPersonProcessor
        from data_collection.utils import Utils
        
        # Initialize processors with memory-conscious settings
        enricher = RedditDataEnricher(ner_model, sentiment_model)
        location_processor = LocationProcessor()
        person_processor = WikipediaPersonProcessor()
        metrics_builder = Utils()
        
        post_file = Path(post_file_path)
        
        # Load and process posts in smaller chunks to reduce memory usage
        with open(post_file, "r", encoding="utf-8") as f:
            posts = json.load(f)
        
        logger.info(f"[PID {process_id}] Processing {len(posts)} posts")
        
        # Process posts in batches to manage memory
        BATCH_SIZE = 50  # Process posts in batches of 50
        enriched_posts = []
        
        for i in range(0, len(posts), BATCH_SIZE):
            batch = posts[i:i + BATCH_SIZE]
            batch_enriched = []
            
            for post in batch:
                try:
                    enriched_post = enricher.enrich_post(post)
                    batch_enriched.append(enriched_post)
                except Exception as e:
                    logger.warning(f"[PID {process_id}] Error enriching post: {e}")
                    batch_enriched.append(post)  # Add without enrichment
            
            enriched_posts.extend(batch_enriched)
            
            # Force garbage collection after each batch
            gc.collect()
            
            # Check memory usage
            current_memory = get_memory_usage()
            if current_memory > initial_memory * 3:  # If memory tripled, force cleanup
                logger.warning(f"[PID {process_id}] High memory usage: {current_memory:.1f}MB")
                gc.collect()
        
        # Process locations and persons
        processed_posts = location_processor.process_posts(enriched_posts)
        processed_posts = person_processor.update_persons_mentioned(processed_posts)
        
        # Clear intermediate data
        del enriched_posts
        gc.collect()
        
        # Load and process comments
        date_str = post_file.stem.replace("posts_", "")
        comment_file = Path(comments_dir) / f"comments_{date_str}.json"
        
        enriched_comments = []
        if comment_file.exists():
            with open(comment_file, "r", encoding="utf-8") as f:
                comments = json.load(f)
            
            logger.info(f"[PID {process_id}] Processing {len(comments)} comments")
            
            # Process comments in batches
            COMMENT_BATCH_SIZE = 100
            for i in range(0, len(comments), COMMENT_BATCH_SIZE):
                batch = comments[i:i + COMMENT_BATCH_SIZE]
                batch_enriched = []
                
                for comment in batch:
                    try:
                        enriched_comment = enricher.enrich_comment(comment)
                        batch_enriched.append(enriched_comment)
                    except Exception as e:
                        logger.warning(f"[PID {process_id}] Error enriching comment: {e}")
                        batch_enriched.append(comment)
                
                enriched_comments.extend(batch_enriched)
                
                # Garbage collection after each batch
                gc.collect()
            
            # Clear comments data
            del comments
            gc.collect()
        
        # Add metrics
        processed_posts = metrics_builder.add_comment_metrics(processed_posts, enriched_comments)
        processed_comments = metrics_builder.add_post_metrics(processed_posts, enriched_comments)
        
        # Save results
        out_post_file = Path(analysis_posts_dir) / f"posts_{date_str}.json"
        out_comment_file = Path(analysis_comments_dir) / f"comments_{date_str}.json"
        
        with open(out_post_file, "w", encoding="utf-8") as f:
            json.dump(processed_posts, f, ensure_ascii=False, indent=2)  # Reduced indent to save space
        
        with open(out_comment_file, "w", encoding="utf-8") as f:
            json.dump(processed_comments, f, ensure_ascii=False, indent=2)
        
        # Final cleanup
        del processed_posts, processed_comments, enriched_comments
        del enricher, location_processor, person_processor, metrics_builder
        gc.collect()
        
        processing_time = time.time() - start_time
        final_memory = get_memory_usage()
        
        logger.info(f"[PID {process_id}] Completed {post_file.name} in {processing_time:.1f}s")
        
        return {
            'file': post_file.name,
            'posts_count': len(posts),
            'comments_count': len(enriched_comments) if 'enriched_comments' in locals() else 0,
            'processing_time': processing_time,
            'success': True,
            'date': date_str,
            'process_id': process_id,
            'initial_memory_mb': initial_memory,
            'final_memory_mb': final_memory,
            'memory_delta_mb': final_memory - initial_memory
        }
        
    except Exception as e:
        logger.error(f"[PID {process_id}] Error processing {Path(post_file_path).name}: {e}")
        
        # Force cleanup on error
        gc.collect()
        
        return {
            'file': Path(post_file_path).name,
            'error': str(e),
            'success': False,
            'processing_time': time.time() - start_time,
            'process_id': process_id,
            'initial_memory_mb': initial_memory,
            'final_memory_mb': get_memory_usage()
        }

def run_memory_efficient_parallel(data_dir: str = "data", analysis_dir: str = "analysis", 
                                 max_workers: Optional[int] = None, file_pattern: str = "*.json",
                                 batch_size: Optional[int] = None) -> dict:
    """
    Run memory-efficient parallel processing with batching and resource monitoring.
    
    Args:
        data_dir: Directory containing input data
        analysis_dir: Directory for output analysis
        max_workers: Maximum number of parallel workers (auto-detected if None)
        file_pattern: Pattern to match files
        batch_size: Number of files to process per batch (auto-calculated if None)
    """
    print(f"🚀 Starting memory-efficient parallel processing at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Setup directories
    data_path = Path(data_dir)
    posts_dir = data_path / "posts"
    comments_dir = data_path / "comments"
    analysis_path = Path(analysis_dir)
    analysis_posts_dir = analysis_path / "posts"
    analysis_comments_dir = analysis_path / "comments"
    
    # Create output directories
    analysis_posts_dir.mkdir(parents=True, exist_ok=True)
    analysis_comments_dir.mkdir(parents=True, exist_ok=True)
    
    # Get environment variables
    ner_model = os.getenv("NER_MODEL")
    sentiment_model = os.getenv("SENTIMENT_MODEL")
    
    if not ner_model or not sentiment_model:
        raise ValueError("Please set NER_MODEL and SENTIMENT_MODEL environment variables")
    
    # Find files to process
    post_files = sorted(posts_dir.glob(file_pattern))
    
    if not post_files:
        print(f"❌ No files found matching pattern '{file_pattern}' in {posts_dir}")
        return None
    
    print(f"📁 Found {len(post_files)} files to process")
    
    # Memory-conscious worker and batch size calculation
    available_memory_gb = psutil.virtual_memory().available / (1024**3)
    cpu_count = psutil.cpu_count()
    
    if max_workers is None:
        # Conservative worker count based on available memory
        # Assume each worker needs ~2GB for models + data
        max_workers = min(2, max(1, int(available_memory_gb // 3)))
    
    if batch_size is None:
        # Process files in batches to avoid overwhelming the system
        batch_size = max(2, min(5, len(post_files) // 2))
    
    print(f"🧠 Using models: NER={ner_model}, Sentiment={sentiment_model}")
    print(f"💾 Available memory: {available_memory_gb:.1f}GB")
    print(f"🔧 Configuration: {max_workers} workers, batch size {batch_size}")
    
    # Process files in batches
    all_results = []
    failed_files = []
    total_start_time = time.time()
    
    # Split files into batches
    file_batches = [post_files[i:i + batch_size] for i in range(0, len(post_files), batch_size)]
    
    for batch_idx, file_batch in enumerate(file_batches, 1):
        print(f"\n📦 Processing batch {batch_idx}/{len(file_batches)} ({len(file_batch)} files)")
        
        # Check system resources before starting batch
        if not monitor_system_resources():
            print("⚠️ System resources too high, pausing...")
            time.sleep(30)
            gc.collect()
            
            if not monitor_system_resources():
                print("❌ Stopping due to high resource usage")
                break
        
        # Prepare arguments for this batch
        batch_args = [
            (str(post_file), str(comments_dir), str(analysis_posts_dir),
             str(analysis_comments_dir), ner_model, sentiment_model)
            for post_file in file_batch
        ]
        
        # Process batch with limited workers
        batch_start_time = time.time()
        batch_results = []
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks in the batch
            future_to_file = {
                executor.submit(process_single_file_safe, args): args[0]
                for args in batch_args
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    batch_results.append(result)
                    
                    if result['success']:
                        print(f"✅ {result['file']} - {result['posts_count']} posts, "
                              f"{result['comments_count']} comments, "
                              f"{result['processing_time']:.1f}s, "
                              f"Δmem: {result['memory_delta_mb']:.1f}MB")
                    else:
                        failed_files.append(result['file'])
                        print(f"❌ {result['file']} - {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    file_name = Path(file_path).name
                    failed_files.append(file_name)
                    print(f"❌ {file_name} - Exception: {e}")
                    batch_results.append({
                        'file': file_name,
                        'error': str(e),
                        'success': False,
                        'processing_time': 0
                    })
        
        all_results.extend(batch_results)
        
        batch_time = time.time() - batch_start_time
        successful_in_batch = sum(1 for r in batch_results if r['success'])
        
        print(f"📊 Batch {batch_idx} completed: {successful_in_batch}/{len(file_batch)} files in {batch_time:.1f}s")
        
        # Force garbage collection between batches
        gc.collect()
        
        # Brief pause between batches to let system recover
        if batch_idx < len(file_batches):
            time.sleep(2)
    
    # Calculate final statistics
    total_time = time.time() - total_start_time
    successful_results = [r for r in all_results if r['success']]
    total_posts = sum(r.get('posts_count', 0) for r in successful_results)
    total_comments = sum(r.get('comments_count', 0) for r in successful_results)
    avg_processing_time = sum(r['processing_time'] for r in successful_results) / len(successful_results) if successful_results else 0
    
    summary = {
        'total_files': len(post_files),
        'successful_files': len(successful_results),
        'failed_files': len(failed_files),
        'failed_file_names': failed_files,
        'total_posts_processed': total_posts,
        'total_comments_processed': total_comments,
        'total_processing_time': total_time,
        'average_file_processing_time': avg_processing_time,
        'files_per_second': len(successful_results) / total_time if total_time > 0 else 0,
        'batches_processed': len(file_batches),
        'workers_used': max_workers,
        'batch_size_used': batch_size,
        'results': all_results
    }
    
    # Print comprehensive summary
    print(f"\n✅ Processing completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Final Summary:")
    print(f"   • Files processed: {summary['successful_files']}/{summary['total_files']}")
    print(f"   • Posts processed: {summary['total_posts_processed']:,}")
    print(f"   • Comments processed: {summary['total_comments_processed']:,}")
    print(f"   • Total time: {summary['total_processing_time']:.1f}s")
    print(f"   • Average time per file: {summary['average_file_processing_time']:.1f}s")
    print(f"   • Processing rate: {summary['files_per_second']:.1f} files/second")
    print(f"   • Batches processed: {summary['batches_processed']}")
    print(f"   • Configuration: {max_workers} workers, batch size {batch_size}")
    
    if failed_files:
        print(f"❌ Failed files ({len(failed_files)}):")
        for failed_file in failed_files[:10]:  # Show first 10 failures
            print(f"   • {failed_file}")
        if len(failed_files) > 10:
            print(f"   • ... and {len(failed_files) - 10} more")
    
    return summary

# Convenience functions for different use cases
def quick_process_safe(max_workers=1, batch_size=3):
    """Conservative processing with minimal resource usage"""
    return run_memory_efficient_parallel(max_workers=max_workers, batch_size=batch_size)

def process_recent_files_safe(days=7, max_workers=1, batch_size=2):
    """Process recent files with conservative settings"""
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=days)
    pattern = f"posts_{cutoff_date.strftime('%Y-%m')}*.json"
    return run_memory_efficient_parallel(
        max_workers=max_workers, 
        batch_size=batch_size,
        file_pattern=pattern
    )

def process_single_date_safe(date_str, max_workers=1):
    """Process files for a specific date safely"""
    pattern = f"posts_{date_str}.json"
    return run_memory_efficient_parallel(
        max_workers=max_workers, 
        batch_size=1,
        file_pattern=pattern
    )

if __name__ == "__main__":
    # Example usage with conservative settings
    summary = quick_process_safe(max_workers=2, batch_size=3)