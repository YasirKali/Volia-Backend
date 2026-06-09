import instaloader
import sys

def test_instaloader_post(shortcode):
    print(f"\n==========================================")
    print(f"Testing Instaloader for shortcode: {shortcode}")
    print(f"==========================================")
    
    L = instaloader.Instaloader()
    
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        print(f"Owner Profile: {post.owner_profile.username}")
        print(f"Caption: {post.caption[:100]}...")
        print(f"Post Type: {post.typename}")
        
        if post.typename == 'GraphSidecar':
            print("This is a carousel post!")
            nodes = list(post.get_sidecar_nodes())
            print(f"Number of slides/nodes: {len(nodes)}")
            for idx, node in enumerate(nodes):
                print(f"  Slide {idx}: is_video={node.is_video}, display_url={node.display_url[:90]}...")
                if node.is_video:
                    print(f"    Video URL: {node.video_url[:90]}...")
        elif post.typename == 'GraphImage':
            print("This is a single image post!")
            print(f"Image URL: {post.url[:90]}...")
        elif post.typename == 'GraphVideo':
            print("This is a single video post!")
            print(f"Video URL: {post.video_url[:90]}...")
            print(f"Thumbnail URL: {post.url[:90]}...")
            
    except Exception as e:
        print(f"Error extracting shortcode {shortcode}: {e}")

if __name__ == "__main__":
    # Test shortcode
    test_instaloader_post("C7Wb4XqORz5")
