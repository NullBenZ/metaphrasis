program heat1d
  implicit none
  integer, parameter :: nx=8, nt=3
  integer :: i, n
  real :: dx=1.0, dt=0.1, alpha=0.1
  real :: u(0:nx+1), unew(0:nx+1)
  u=0.0
  u(4)=1.0
  do n=1,nt
    do i=1,nx
      unew(i)=u(i)+alpha*dt/(dx*dx)*(u(i+1)-2.0*u(i)+u(i-1))
    end do
    unew(0)=u(0)
    unew(nx+1)=u(nx+1)
    u=unew
  end do
  open(unit=20,file='result.txt',status='replace')
  do i=0,nx+1
    write(20,'(ES24.16)') u(i)
  end do
  close(20)
end program heat1d
