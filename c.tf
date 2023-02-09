resource "aws_security_group" "global-test" {
  name = "global-test"
  description = "global rule"

ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

