from rllab import config
import os


if __name__ == "__main__":
    os.system("""
        aws s3 sync {remote_dir} {local_dir} --content-type "UTF-8"
    """.format(local_dir=os.path.join(config.LOG_DIR, "s3"), remote_dir=config.AWS_S3_PATH))