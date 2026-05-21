program fibonacci
  integer :: a, b, c, i
  print *, 'Fibonacci sequence (first 15 terms):'
  a = 0
  b = 1
  do i = 1, 15
    print *, a
    c = a + b
    a = b
    b = c
  end do
end program fibonacci
