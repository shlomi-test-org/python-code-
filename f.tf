
resource "aws_s3_bucket" "positive1" {
  bucket = "example"
}

resource "aws_s3_bucket_public_access_block" "positive3" {
  bucket = aws_s3_bucket.example.id

  block_public_policy = true
  ignore_public_acls  = true
  restrict_public_buckets = false
}
