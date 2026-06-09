import instaloader

def test_instagram_extract(shortcode):
    L = instaloader.Instaloader()
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        print("Title/Caption:", post.caption)
        print("Uploader:", post.owner_username)
        
        # Check if it has multiple images
        if post.typename == 'GraphSidecar':
            print("Type: Sidecar (Multiple Images/Videos)")
            for idx, node in enumerate(post.get_sidecar_nodes()):
                print(f"Node {idx}: is_video={node.is_video}, url={node.display_url}")
        else:
            print("Type: Single Media")
            print(f"Is Video: {post.is_video}")
            print(f"URL: {post.video_url if post.is_video else post.url}")
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_instagram_extract("DZUvY1ECokg")
