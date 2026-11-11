program unsupported_function
  implicit none
  integer, parameter :: nx=8, nt=2
  integer :: i,n
  real :: u(0:nx+1), unew(0:nx+1), dt=0.1
  do n=1,nt
    do i=1,nx
      unew(i)=u(i)+dt*(sin(u(i+1))-2.0*u(i)+u(i-1))
    end do
    unew(0)=u(0)
    unew(nx+1)=u(nx+1)
    u=unew
  end do
end program unsupported_function
