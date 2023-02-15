resource "aws_lb_listener" "listener54356" {
  load_balancer_arn = aws_lb.test3.arn
  port = 80
  default_action {
    type = "redirect"

    redirect {
      port        = "80"
      protocol    = "HTTP"
      status_code = "HTTP_301"
    }
  }
}
