resource "aws_s3_bucket" "example_bucket" {
  bucket        = "my-tf-test-bucket"
  acl           = "public-read-write"
  force_destroy = true
}
