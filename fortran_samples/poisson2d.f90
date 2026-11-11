program poisson2d
  implicit none
  integer, parameter :: nx=6, ny=5, niter=4
  integer :: i,j,iter
  real :: h2=1.0
  real :: u(0:nx+1,0:ny+1), unew(0:nx+1,0:ny+1), f(0:nx+1,0:ny+1)
  u=0.0
  f=1.0
  do iter=1,niter
    do j=1,ny
      do i=1,nx
        unew(i,j)=0.25*(u(i+1,j)+u(i-1,j)+u(i,j+1)+u(i,j-1)-h2*f(i,j))
      end do
    end do
    unew(0,:)=u(0,:)
    unew(nx+1,:)=u(nx+1,:)
    unew(:,0)=u(:,0)
    unew(:,ny+1)=u(:,ny+1)
    u=unew
  end do
  open(unit=20,file='result.txt',status='replace')
  do j=0,ny+1
    do i=0,nx+1
      write(20,'(ES24.16)') u(i,j)
    end do
  end do
  close(20)
end program poisson2d
