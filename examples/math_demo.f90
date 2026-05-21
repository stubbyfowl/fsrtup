program math_demo
  real :: pi, e
  integer :: i
  pi = 3.14159265358979
  e  = 2.71828182845905

  print *, '=== Math Demo ==='
  print *, 'sin(pi/4) =', sin(pi/4.0)
  print *, 'cos(pi/4) =', cos(pi/4.0)
  print *, 'tan(pi/4) =', tan(pi/4.0)
  print *, 'sqrt(2)   =', sqrt(2.0)
  print *, '2**10     =', 2**10
  print *, 'exp(1)    =', exp(1.0)
  print *, 'log(e)    =', log(e)

  print *, ''
  do i = 1, 10
    print *, i, '! =', factorial(i)
  end do
end program math_demo

integer function factorial(n)
  integer, intent(in) :: n
  integer :: i
  factorial = 1
  do i = 2, n
    factorial = factorial * i
  end do
end function factorial
