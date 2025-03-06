import os
import re
import json
import hashlib
import shutil
from github import Github
from pathlib import Path

# 新增配置文件路径
CONFIG_FILE = Path.home() / ".image_upload_config.json"

def load_github_token():
    """从本地配置文件加载GitHub Token"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            token = config.get("GITHUB_TOKEN")
            if not token:
                raise ValueError("配置文件中缺少GITHUB_TOKEN字段")
            return token
    except FileNotFoundError:
        print(f"错误：配置文件 {CONFIG_FILE} 不存在。请创建该文件并包含GITHUB_TOKEN字段。")
        exit(1)
    except json.JSONDecodeError:
        print(f"错误：配置文件格式不正确，应为有效的JSON格式。")
        exit(1)
    except Exception as e:
        print(f"读取配置文件出错: {str(e)}")
        exit(1)

# 配置项
CONFIG = {
    "GITHUB_TOKEN": load_github_token(),  # 从配置文件加载
    "REPO": "qingyun201908/qingyun201908.github.io",
    "BRANCH": "images",
    "POSTS_DIR": r"D:\2025Blog\my-blog\source\_posts",
    "ALLOWED_EXTENSIONS": {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'},
    "HASH_STORE": Path.home() / ".image_upload_processed",
    "LOCAL_IMAGES_DIR": None,  # 将在主程序中初始化
}

class FileProcessor:
    def __init__(self):
        self.processed = self.load_processed()
        self.repo = self.init_github()
        print(f"成功连接仓库: {self.repo.full_name}\n")

    def init_github(self):
        """初始化 GitHub 连接"""
        try:
            g = Github(CONFIG["GITHUB_TOKEN"])
            return g.get_repo(CONFIG["REPO"])
        except Exception as e:
            print(f"GitHub 连接失败: {e}")
            exit(1)

    def load_processed(self):
        """加载已处理记录"""
        try:
            if CONFIG["HASH_STORE"].exists():
                with open(CONFIG["HASH_STORE"], 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载处理记录失败: {e}")
        return {}

    def save_processed(self):
        """保存处理记录"""
        try:
            with open(CONFIG["HASH_STORE"], 'w') as f:
                json.dump(self.processed, f, indent=2)
        except Exception as e:
            print(f"保存处理记录失败: {e}")

    def calculate_hash(self, filepath):
        """计算文件哈希值"""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def is_file_modified(self, filepath):
        """检查文件是否修改过"""
        current_hash = self.calculate_hash(filepath)
        stored_hash = self.processed.get(str(filepath))
        return current_hash != stored_hash

    def update_hash(self, filepath):
        """更新文件哈希记录"""
        self.processed[str(filepath)] = self.calculate_hash(filepath)

    def process_directory(self):
        """处理整个目录"""
        try:
            all_articles = self.get_markdown_files()
            print(f"发现 {len(all_articles)} 篇待处理文章")
            success_count = 0
            
            for idx, path in enumerate(all_articles, 1):
                print(f"\n▶▶ 正在处理文章 ({idx}/{len(all_articles)}) ◀◀")
                article = ArticleProcessor(path, self)
                if article.process():
                    success_count += 1
                    self.update_hash(path)

            print(f"\n处理完成！成功处理 {success_count}/{len(all_articles)} 篇文章")
            self.save_processed()
        except Exception as e:
            print(f"目录处理失败: {str(e)}")
            exit(1)

    def get_markdown_files(self):
        """获取所有 Markdown 文件"""
        md_files = []
        for root, _, files in os.walk(CONFIG["POSTS_DIR"]):
            for file in files:
                if file.endswith(".md"):
                    md_files.append(Path(root) / file)
        return md_files

class ArticleProcessor:
    def __init__(self, path, manager):
        self.path = Path(path)
        self.manager = manager
        self.content = None
        self.modified = False

    @property
    def article_folder(self):
        """获取文章对应的文件夹名称"""
        return self.path.stem

    def process(self):
        """处理单个文章"""
        if not self.should_process():
            print(f"文件未修改，跳过处理: {self.path.name}")
            return False

        print(f"\n{'='*40}")
        print(f"正在处理文章: {self.path.name}")
        print(f"完整路径: {self.path}\n{'-'*40}")

        try:
            self.load_content()
            self.process_images()
            self.save_content()
            return True
        except Exception as e:
            print(f"处理文章失败: {str(e)}")
            return False
        finally:
            print(f"{'='*40}\n")

    def should_process(self):
        """检查是否需要处理"""
        if not self.path.exists():
            raise FileNotFoundError(f"文件不存在: {self.path}")
        return self.manager.is_file_modified(self.path)

    def load_content(self):
        """加载文章内容"""
        with open(self.path, 'r', encoding='utf-8') as f:
            self.content = f.read().replace("\\", "/")

    def process_images(self):
        """处理图片引用"""
        matches = re.findall("!\[.*?\]\((.*?)\)", self.content)
        print(f"发现 {len(matches)} 个图片引用")

        for i, local_path in enumerate(matches, 1):
            print(f"\n处理进度 ({i}/{len(matches)})")
            print(f"原始路径: {local_path}")
            
            if self.process_single_image(local_path):
                self.modified = True

    def process_single_image(self, local_path):
        """处理单个图片"""
        if local_path.startswith("http"):
            print("↳ 跳过网络图片")
            return False

        try:
            win_path = self.validate_image_path(local_path)
            if not self.is_valid_image(win_path):
                return False

            # 保存到本地目录
            self.save_image_locally(win_path)
            
            new_url = self.upload_image(win_path)
            if new_url:
                self.content = self.content.replace(local_path, new_url)
                print(f"替换成功: {new_url}")
                return True
        except FileNotFoundError as e:
            print(f"↳ 路径错误: {str(e)}")
        return False

    def validate_image_path(self, path):
        """验证并转换图片路径"""
        win_path = Path(str(path).replace("/", "\\"))
        if not win_path.is_absolute():
            win_path = self.path.parent / win_path
        if not win_path.exists():
            raise FileNotFoundError(win_path)
        return win_path

    def is_valid_image(self, path):
        """验证图片格式"""
        ext = path.suffix.lower()
        if ext not in CONFIG["ALLOWED_EXTENSIONS"]:
            print("↳ 跳过非图片文件")
            return False
        return True

    def save_image_locally(self, image_path):
        """保存图片到本地目录"""
        try:
            local_dir = CONFIG["LOCAL_IMAGES_DIR"] / self.article_folder
            local_dir.mkdir(parents=True, exist_ok=True)
            
            target_path = local_dir / image_path.name
            
            # 检查文件是否存在且内容相同
            if not target_path.exists() or target_path.read_bytes() != image_path.read_bytes():
                shutil.copy2(image_path, target_path)
                print(f"图片已保存到本地: {target_path}")
        except Exception as e:
            print(f"本地保存失败: {str(e)}")

    def upload_image(self, image_path):
        """上传图片到 GitHub"""
        try:
            image_name = image_path.name
            remote_path = f"images/{self.article_folder}/{image_name}"
            
            with open(image_path, 'rb') as f:
                content = f.read()

            try:
                existing = self.manager.repo.get_contents(remote_path, CONFIG["BRANCH"])
                if existing.decoded_content == content:
                    print(f"图片已存在，跳过上传: {remote_path}")
                    return f"{CONFIG['BASE_URL']}{remote_path}"
                self.manager.repo.update_file(
                    path=remote_path,
                    message=f"Update image: {remote_path}",
                    content=content,
                    sha=existing.sha,
                    branch=CONFIG["BRANCH"]
                )
                print(f"已更新: {remote_path}")
            except Exception:  # 文件不存在
                self.manager.repo.create_file(
                    path=remote_path,
                    message=f"Add image: {remote_path}",
                    content=content,
                    branch=CONFIG["BRANCH"]
                )
                print(f"已上传: {remote_path}")

            return f"{CONFIG['BASE_URL']}{remote_path}"
        except Exception as e:
            print(f"上传失败: {e}")
            return None

    def save_content(self):
        """保存修改后的内容"""
        if self.modified:
            with open(self.path, 'w', encoding='utf-8') as f:
                f.write(self.content.replace("/", "\\"))
            print("\n文章更新完成 ✓")
        else:
            print("\n未发现需要修改的内容 ◯")

if __name__ == "__main__":
    # 初始化配置项
    CONFIG["POSTS_DIR"] = Path(CONFIG["POSTS_DIR"])
    CONFIG["LOCAL_IMAGES_DIR"] = CONFIG["POSTS_DIR"].parent / "images"
    CONFIG["BASE_URL"] = f"https://raw.githubusercontent.com/{CONFIG['REPO']}/{CONFIG['BRANCH']}/"
    
    processor = FileProcessor()
    processor.process_directory()