
resource "aws_redshift_cluster" "positive1" {
  cluster_identifier = "tf-redshift-cluster"
  database_name      = "mydb"
  
  master_username    = "foo"
  node_type          = "dc1.large"
  cluster_type       = "single-node"
}



resource "aws_redshift_cluster" "positive2" {
  cluster_identifier = "tf-redshift-cluster"
  database_name      = "mydb"
  master_username    = "foo"
  node_type          = "dc1.large"
  cluster_type       = "sinaaaglt-node"
  encrypted          = true
  
}












