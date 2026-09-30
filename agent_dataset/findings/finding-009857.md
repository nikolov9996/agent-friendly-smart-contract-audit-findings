---
id: 9857
severity: "High"
---

# No LSTs transfer on node operator withdrawals resulting in stuck funds and loss for node operators

## Description

```solidity
// stores the LST share balance for each operator
mapping(address => uint256) private shareBalances;
// total number of LST shares staked in this pool
uint256 private totalShares;
```
Upon withdrawing (OperatorStakingPool:_withdraw:L200-204) sharesBalances and totalShares are updated but no LST is transferred from OperatorStakingPool back to operator. This leaves OperatorStakingPool with stuck LST tokens and node operators can't withdraw their stake.
```solidity
function withdraw(uint256 _amount) external {
    if (!isOperator(msg.sender)) revert SenderNotAuthorized();
    withdraw(msg.sender, _amount);
}

function withdraw(address operator, uint256 _amount) private {
    uint256 sharesAmount = lst.getSharesByStake(_amount);
    shareBalances[operator] -= sharesAmount;
    totalShares -= sharesAmount;

    emit Withdraw(operator, _amount, sharesAmount);
}
```
Vulnerable code: <https://github.com/Cyfrin/2024-09-stakelink/blob/main/contracts/linkStaking/OperatorStakingPool.sol#L199>

Likelihood: High

This will happen on every call to withdraw function inside OperatorStakingPool. Also when owner calls removeOperators function which will call underlying withdraw method if operator has some stake.

Impact: Medium

Operators won't be able to retrieve their staked LSTs, and the funds will be temporarily locked inside the OperatorStakingPool. One way to handle this issue in production would be for the owner to upgrade this implementation with a new one that withdraws all stuck funds. By reviewing past Withdraw events, the owner could redistribute the funds back to the operators.

## Proof of Concept

```TypeScript
it('PoC:High:OperatorStakingPool.sol#L199-204=>No LSTs transfer on node operator withdrawals resulting in stuck funds', async () => {
    const { signers, accounts, opPool, lst } = await loadFixture(deployFixture)
    const operator = signers[0]
    const operatorDepositAmount = toEther(1000)

    // 1. ========= Deposit to operator staking pool =========

    // take snapshot of operator balance before deposit
    const operatorBalanceBeforeDeposit = await lst.balanceOf(operator.address)
    // take snapshot of operator staking pool balance before deposit
    const opStakingPoolBalanceBeforeDeposit = await lst.balanceOf(opPool.target)

    // deposit to operator staking pool
    await lst.connect(operator).transferAndCall(opPool.target, operatorDepositAmount, '0x')

    // take snapshot of operator balance after deposit
    const operatorBalanceAfterDeposit = await lst.balanceOf(operator.address)
    // take snapshot of operator staking pool balance after deposit
    const opStakingPoolBalanceAfterDeposit = await lst.balanceOf(opPool.target)

    // make sure operator balance decreased by the deposit amount
    assert.equal(operatorBalanceBeforeDeposit - operatorBalanceAfterDeposit, operatorDepositAmount)
    // make sure operator staking pool balance increased by the deposit amount
    assert.equal(opStakingPoolBalanceAfterDeposit, opStakingPoolBalanceBeforeDeposit + operatorDepositAmount)

    // 2. ========= Withdraw from operator staking pool =========
    
    // take snapshot of operator balance before withdraw
    const operatorBalanceBeforeWithdraw = await lst.balanceOf(operator.address)
    // take snapshot of operator staking pool balance before withdraw
    const opStakingPoolBalanceBeforeWithdraw = await lst.balanceOf(opPool.target)

    // withdraw from operator staking pool
    await opPool.connect(operator).withdraw(operatorDepositAmount)

    // take snapshot of operator balance after withdraw
    const operatorBalanceAfterWithdraw = await lst.balanceOf(operator.address)
    // take snapshot of operator staking pool balance after withdraw
    const opStakingPoolBalanceAfterWithdraw = await lst.balanceOf(opPool.target)

    // make sure operator principal is 0
    assert.equal(fromEther(await opPool.getOperatorPrincipal(accounts[0])), 0)
    // make sure operator staked is 0
    assert.equal(fromEther(await opPool.getOperatorStaked(accounts[0])), 0)

    // show that operator LST balance didn't change
    assert.equal(operatorBalanceAfterWithdraw, operatorBalanceBeforeWithdraw)
    // show that operator staking pool has the same balance as before the withdraw
    assert.equal(opStakingPoolBalanceAfterWithdraw, opStakingPoolBalanceBeforeWithdraw)
})
```
Running Poc:  
Copy test to ./test/linkStaking/operator-staking-pool.test.ts  
Run tests with npx hardhat test ./test/linkStaking/operator-staking-pool.test.ts --network hardhat

Output:
```Solidity
OperatorStakingPool
    ✔ PoC:High:OperatorStakingPool.sol#L200-204=>No LSTs transfer on operator withdrawals resulting in stuck funds (1499ms)
```

## Recommendation

```diff
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "../core/interfaces/IStakingPool.sol";

contract OperatorStakingPool is Initializable, UUPSUpgradeable, OwnableUpgradeable {
    using SafeERC20Upgradeable for IERC20Upgradeable;
    using SafeERC20 for IERC20;
  
    ...
  
    /**
     * @notice Withdraws tokens
     * @param _operator address of operator with withdraw for
     * @param _amount amount to withdraw
     **/
    function withdraw(address operator, uint256 _amount) private {
        uint256 sharesAmount = lst.getSharesByStake(_amount);
        shareBalances[operator] -= sharesAmount;
        totalShares -= sharesAmount;
        IERC20(address(lst)).safeTransfer(operator, _amount);

        emit Withdraw(operator, _amount, sharesAmount);
    }
```
Medium Risk Findings

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a missing token transfer in the operator withdrawal routine of a liquid‑staking pool. When an operator calls the withdraw function, the contract correctly calculates the number of shares to redeem, decrements the operator's share balance and the pool's total share counter, and emits a Withdraw event, but it never moves the underlying LST tokens from the pool contract back to the operator's address. The root cause is an incomplete implementation: the code updates internal accounting state but omits the external ERC‑20 transfer that should accompany a withdrawal. An attacker does not gain additional privileges, however the bug can be exploited by any operator who attempts to withdraw, because the call will appear successful while the operator's external token balance remains unchanged. The exploit scenario is straightforward: the operator initiates a withdrawal, the contract records a zero principal and zero staked amount for that operator, the event log shows a successful withdrawal, yet the LST tokens stay locked inside the pool. From the user's point of view the expectation is that the token balance will increase by the withdrawn amount, but in reality the balance stays the same, leading to confusion and potential panic. This condition occurs on every invocation of the withdraw function, whether called directly by an operator or indirectly via the owner’s removeOperators routine, which also triggers the same internal withdraw logic. The affected parties are the node operators who stake LST tokens and rely on the ability to retrieve their stake, as well as any downstream users of the protocol who assume correct accounting of deposited assets. The issue was discovered during a manual audit and confirmed with a proof‑of‑concept test that compared token balances before and after a withdrawal, revealing that the balances did not change despite the internal state being cleared. The bug is hard to notice because the contract emits the expected event and updates internal variables, giving the impression of a successful operation, while the external token transfer is silently omitted. To remediate the problem, the withdrawal routine should include a safe ERC‑20 transfer of the specified amount to the operator after adjusting share balances, for example by using OpenZeppelin's SafeERC20.safeTransfer. Adding this step restores the invariant that the sum of internal shares and external token holdings remain consistent, prevents funds from becoming permanently locked, and aligns the contract's behavior with the business logic that a withdrawal returns the staked assets to the operator.
