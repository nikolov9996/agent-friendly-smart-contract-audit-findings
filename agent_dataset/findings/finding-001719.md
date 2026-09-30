---
id: 1719
severity: "High"
---

# The incorrect accounting of protocol fee will

## Description

The incorrect accounting of protocol fee will cause double charging fee and wrong distribution of earnings for variable users.
The calculation for a variable user's earnings, when they withdraw where isStarted() and !isEnded()
41c331f1b14545770c1766fc0ee/lido-fiv/contracts/LidoVault.sol#L520-L545
```solidity
uint256 lidoStETHBalance = stakingBalance();
// staking earnings have accumulated on Lido
uint256 currentStakes = stakingShares();
(uint256 currentState, uint256 ethAmountOwed) =
calculateVariableWithdrawState(
    lidoStETHBalance.mulDiv(currentStakes +
    variableToWithdrawnStakingEarningsInShares[msg.sender].mulDiv(lidoStETHBalance, currentStakes)
);
if (ethAmountOwed >= minStETHWithdrawalAmount()) {
    // estimate protocol fee and update total - will actually be applied on withdraw finalization
    uint256 protocolFee = ethAmountOwed.mulDiv(protocolFeeBps, 10000);
    totalProtocolFee += protocolFee;
    uint256 stakesAmountOwed = lido.getSharesByPooledEth(ethAmountOwed);
    withdrawnStakingEarnings += ethAmountOwed - protocolFee;
    withdrawnStakingEarningsInStakes += stakesAmountOwed;
    variableToWithdrawnStakingEarnings[msg.sender] += ethAmountOwed - protocolFee;
    variableToWithdrawnStakingEarningsInShares[msg.sender] += stakesAmountOwed;
    variableToWithdrawnProtocolFee[msg.sender] += protocolFee;
    variableToVaultOngoingWithdrawalRequestIds[msg.sender] =
    requestWithdrawViaETH(
        msg.sender,
        ethAmountOwed
    );
```
earnings also includes the protocol fee. Then ethAmountOwed is converted to shares stakesAmountOwed. Then the shares is added to withdrawnStakingEarningsInStakes and variableToWithdrawnStakingEarningsInShares[msg.sender].
When the vault ends, the variable user's earnings is calculated at
41c331f1b14545770c1766fc0ee/lido-fiv/contracts/LidoVault.sol#L773-L785
```solidity
uint256 stakingShareAmount = 0;
uint256 totalEarnings = vaultEndingETHBalance.mulDiv(withdrawnStakingEarningsInStakes,vaultEndingStakesAmount) - totalProtocolFee + vaultEndedStakingEarnings;
if (totalEarnings > 0) {
    (uint256 currentState, uint256 stakingEarningsShare) =
    calculateVariableWithdrawState(
        totalEarnings,
        variableToWithdrawnStakingEarningsInShares[msg.sender].mulDiv(vaultEndingETHBalance, vaultEndingStakesAmount)
    );
    stakingShareAmount = stakingEarningsShare;
    variableToWithdrawnStakingEarningsInShares[msg.sender] =
    currentState.mulDiv(vaultEndingStakesAmount,vaultEndingETHBalance);
    variableToWithdrawnStakingEarnings[msg.sender] = currentState;
}
```
The variable user's earnings is the variable stakingEarningsShare. stakingEarningsShare is calculated basing on withdrawnStakingEarningsInStakes, variableToWithdrawnStakingEarningsInShares[msg.sender].
We believe by including protocol fee shares in withdrawnStakingEarningsInStakes, variableToWithdrawnStakingEarningsInShares[msg.sender] will cause stakingEarningsShare to be wrongly calculated.
Refer to the attack path and the PoC for a concrete example.
Internal pre-conditions
A variable user withdraws when isStarted() and !isEnded()
External pre-conditions
Attack Path
Let's have a vault with:
• variableSideCapacity = 10 ether
• protocolFeeBps = 2_000 (20%)
• stETHRate = 1 (1 shares equals to 1 stETH)
On the variable side:
• Alice deposits 10 ether
The expected behavior
1. stETHRate = 1.1. Vault's balance (stETH): 110 ether (increased 10% since the beginning).
• Alice withdraws 8 ether. totalProtocolFee = 2 ether
• New vault's balance: 100 ether
2. Vault ends. stETHRate = 1.21. Vault's balance (stETH): 110 ether (increased 10% since the 1.).
• Alice withdraws 8 ether. Protocol fee: 2 ether
• New vault's balance: 100 ether
This is the expected behavior of the vault.
The actual behavior
1. stETHRate = 1.1. Vault's balance (stETH): 110 ether (increased 10% since the beginning).
• Alice withdraws 8 ether. totalProtocolFee = 2 ether
• New vault's balance: 100 ether
2. Vault ends. stETHRate = 1.21. Vault's balance (stETH): 110 ether (increased 10% since the 1.).
• Alice withdraws.
```solidity
uint256 stakingShareAmount = 0;
uint256 totalEarnings = vaultEndingETHBalance.mulDiv(withdrawnStakingEarningsInStakes,vaultEndingStakesAmount) - totalProtocolFee + vaultEndedStakingEarnings;
if (totalEarnings > 0) {
    (uint256 currentState, uint256 stakingEarningsShare) =
    calculateVariableWithdrawState(
        totalEarnings,
        variableToWithdrawnStakingEarningsInShares[msg.sender].mulDiv(vaultEndingETHBalance, vaultEndingStakesAmount)
    );
    stakingShareAmount = stakingEarningsShare;
    variableToWithdrawnStakingEarningsInShares[msg.sender] =
    currentState.mulDiv(vaultEndingStakesAmount,vaultEndingETHBalance);
    variableToWithdrawnStakingEarnings[msg.sender] = currentState;
}
```
In this code
totalEarnings = 110 × 10 = 1:1 100 − 10 = 1:1 − 2 + 10 × 0:8 = 17
stakingEarningsShare = totalEarnings − 10 1:1 × 100 − 10 = 1:1 = 6
She can only withdraw back 6 ether, which is less than 2 ether comparing to the expected behavior. Moreover, this 2 ether is not credited to the protocolFeeReceiver, no one can claim it and it will stuck in the contract.
On the variable side:
• Alice deposits 5 ether
• Bob deposits 5 ether
The expected behavior
1. stETHRate = 1.1. Vault's balance (stETH): 110 ether (increased 10% since the beginning).
• Alice withdraws 4 ether. totalProtocolFee = 1 ether
• New vault's balance: 105 ether
2. Vault ends. stETHRate = 1.21. Vault's balance (stETH): 115.5 ether (increased 10% since the 1.).
• Alice withdraws 4 ether. Protocol fee: 1 ether
• Bob withdraws 10.5 * 0.8 = 8.4 ether. Protocol fee: 10.5 * 0.2 = 2.1 ether
This is the expected behavior of the vault.
The actual behavior
1. stETHRate = 1.1. Vault's balance (stETH): 110 ether (increased 10% since the beginning).
• Alice withdraws 4 ether. totalProtocolFee = 1 ether
• New vault's balance: 105 ether
2. Vault ends. stETHRate = 1.21. Vault's balance (stETH): 115.5 ether (increased 10% since the 1.).
• Alice withdraws
totalEarnings = 115:5 × 5 = 1:1 100 − 5 = 1:1 − 1 + 15:5 × 0:8 = 16:9
stakingEarningsShare = totalEarnings = 2 − 5 1:1 × 115:5 100 − 5 = 1:1 = 2:95
• Bob withdraws
stakingEarningsShare = totalEarnings = 2 − 0 = 8:45
In the current logic comparing to the expected behavior, Alice is charged with 1 ether more protocol fee. The protocolFeeReceiver can not claim this 1 ether more fee, and it will stuck in the contract. Moreover, 0.05 ether earnings of Alice is credited to Bob.
• The variable user, who withdraws when isStarted() and !isEnded(), will be charged more protocol fee when they withdraw when the vault ends
• The exceed protocol fee will be stuck in the contract
• Wrong distribution of the variable earnings

## Proof of Concept

Add a setter in LidoVault.sol to set lido and lidoWithdrawalQueue to the mock version for easier debugging
41c331f1b14545770c1766fc0ee/lido-fiv/contracts/LidoVault.sol#L1003-L1007
```solidity
/// @notice Lido contract
- ILido public constant lido = ILido(0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84);
+ ILido public lido = ILido(0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84);
/// @notice Lido withdrawal queue contract
- ILidoWithdrawalQueueERC721 public constant lidoWithdrawalQueue = ILidoWithdrawalQueueERC721(0x889edC2eDab5f40e902b864aD4d7AdE8E412F9B1);
+ ILidoWithdrawalQueueERC721 public lidoWithdrawalQueue = ILidoWithdrawalQueueERC721(0x889edC2eDab5f40e902b864aD4d7AdE8E412F9B1);
+ function setLidoInfo(address _lido, address _withdrawalQueue) public {
+   lido = ILido(_lido);
+   lidoWithdrawalQueue = ILidoWithdrawalQueueERC721(_withdrawalQueue);
+ }
```
Run command: forge test --match-path test/PoC.t.sol -vv
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.18;
import { VaultFactory } from "contracts/VaultFactory.sol";
import { LidoVault } from "contracts/LidoVault.sol";
import { Test, console } from "forge-std/Test.sol";
contract MockLido {
    uint256 public rate;
    mapping(address => uint256) private _sharesOf;
    constructor() {
        rate = 1e27;
    }
    function submit(address _referral) external payable returns (uint256) {
        uint256 shares = msg.value * 1e27 / rate;
        _sharesOf[msg.sender] += shares;
        return shares;
    }
    function approve(address spender, uint256 amount) external returns (bool) {
        return true;
    }
    function getPooledEthByShares(uint256 _sharesAmount) external view returns (uint256) {
        return _sharesAmount * rate / 1e27;
    }
    function getSharesByPooledEth(uint256 _ethAmount) external view returns (uint256) {
        return _ethAmount * 1e27 / rate;
    }
    function balanceOf(address _account) external view returns (uint256) {
        return _sharesOf[_account] * rate / 1e27;
    }
    function sharesOf(address _account) external view returns (uint256) {
        return _sharesOf[_account];
    }
    function setRate(uint256 _rate) external {
        rate = _rate;
    }
    function burnShares(uint256 _amount, address _owner) external {
        uint256 shares = _amount * 1e27 / rate;
        _sharesOf[_owner] -= shares;
    }
}
contract MockLidoWithdrawalQueueERC721 {
    MockLido public lido;
    mapping(uint256 requestId => uint256 amount) public requestIdToAmount;
    uint256 public currentRequestId;
    constructor(address _lido) {
        lido = MockLido(_lido);
    }
    function claimWithdrawal(uint256 _requestId) external {
        payable(msg.sender).call{value: requestIdToAmount[_requestId]}("");
    }
    function requestWithdrawals(uint256[] calldata _amounts, address _owner) external returns (uint256[] memory requestIds) {
        lido.burnShares(_amounts[0], _owner);
        requestIdToAmount[currentRequestId] = _amounts[0];
        requestIds = new uint256[](1);
        requestIds[0] = currentRequestId++;
    }
    receive() external payable {
    }
}
contract PoC is Test {
    MockLido lido;
    MockLidoWithdrawalQueueERC721 lidoWithdrawalQueueERC721;
    VaultFactory factory;
    LidoVault vault;
    address alice = makeAddr('alice');
    address bob = makeAddr('bob');
    address feeReceiver = makeAddr('feeReceiver');
    uint256 protocolFeeBps = 2_000;
    uint256 variableCap = 10 ether;
    function setUp() public {
        lido = new MockLido();
        lidoWithdrawalQueueERC721 = new MockLidoWithdrawalQueueERC721(address(lido));
        factory = new VaultFactory(protocolFeeBps, 0);
        factory.setProtocolFeeReceiver(feeReceiver);
        (,address addr) = factory.vaultInfo(1);
        vault = LidoVault(payable(addr));
        vault.setLidoInfo(address(lido), address(lidoWithdrawalQueueERC721));
        vm.deal(address(lidoWithdrawalQueueERC721), 1000 ether);
    }
    function testFirstVulnerabilityPath() public {
        vm.deal(alice, variableCap);
        vm.prank(alice);
        vault.deposit{value: alice.balance}(1);
        lido.setRate(1.1e27);
        vm.startPrank(alice);
        vault.withdraw(1);
        vault.finalizeVaultOngoingVariableWithdrawals();
        vm.stopPrank();
        console.log("Alice's balance after first claim: %e", alice.balance);
        skip(1 days + 1);
        lido.setRate(1.21e27);
        vm.startPrank(alice);
        vault.withdraw(1);
        vault.finalizeVaultEndedWithdrawals(1);
        vm.stopPrank();
        console.log("Alice's balance at the end: %e", alice.balance);
        vm.prank(feeReceiver);
        vault.withdraw(1);
        vault.withdraw(0);
        vm.stopPrank();
        console.log("Vault's balance at the end: %e", address(vault).balance);
    }
    function testSecondVulnerabilityPath() public {
        vm.deal(alice, variableCap / 2);
        vm.deal(bob, variableCap / 2);
        vm.prank(alice);
        vault.deposit{value: alice.balance}(1);
        vm.prank(bob);
        vault.deposit{value: bob.balance}(1);
        lido.setRate(1.1e27);
        vm.startPrank(alice);
        vault.withdraw(1);
        vault.finalizeVaultOngoingVariableWithdrawals();
        vm.stopPrank();
        console.log("Alice's balance after first claim: %e", alice.balance);
        skip(1 days + 1);
        lido.setRate(1.21e27);
        vm.startPrank(alice);
        vault.withdraw(1);
        vault.finalizeVaultEndedWithdrawals(1);
        vm.stopPrank();
        vm.prank(bob);
        vault.withdraw(1);
        console.log("Alice's balance at the end: %e", alice.balance);
        console.log("Bob's balance at the end: %e", bob.balance);
        vm.prank(feeReceiver);
        vault.withdraw(1);
        vault.withdraw(0);
        vm.stopPrank();
        console.log("Vault's balance at the end: %e", address(vault).balance);
    }
}
```
testFirstVulnerabilityPath()
Logs:
Alice's balance after first claim: 8e18
Alice's balance at the end: 1.4e19
Vault's balance at the end: 2e18
ETH left in the contract.
testSecondVulnerabilityPath()
Logs:
Alice's balance after first claim: 4e18
Alice's balance at the end: 6.95e18
Bob's balance at the end: 8.449999999999999999e18
Vault's balance at the end: 1.000000000000000001e18
ETH left in the contract.

## Recommendation

```solidity
stakesAmountOwed at LidoVault.sol:534 should exclude the protocolFee
uint256 protocolFee = ethAmountOwed.mulDiv(protocolFeeBps, 10000);
totalProtocolFee += protocolFee;
- uint256 stakesAmountOwed = lido.getSharesByPooledEth(ethAmountOwed);
+ uint256 stakesAmountOwed = lido.getSharesByPooledEth(ethAmountOwed - protocolFee);
```
```solidity
totalEarnings at LidoVault.sol:775 should exclude the deduction of totalProtocolFee
- uint256 totalEarnings = vaultEndingETHBalance.mulDiv(withdrawnStakingEarningsInStakes,vaultEndingStakesAmount) - totalProtocolFee + vaultEndedStakingEarnings;
+ uint256 totalEarnings = vaultEndingETHBalance.mulDiv(withdrawnStakingEarningsInStakes,vaultEndingStakesAmount) + vaultEndedStakingEarnings;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect accounting of the protocol fee inside the LidoVault contract that results in a double‑charging of the fee and an erroneous distribution of earnings for users who hold variable positions. The root cause is that the protocol fee, which is deducted from the amount owed to a withdrawing user, is still represented as staking shares and added to the global variable "withdrawnStakingEarningsInStakes" as well as to the per‑user mapping "variableToWithdrawnStakingEarningsInShares". When the vault later reaches its ending phase, the contract computes the total earnings for each variable user by multiplying the vault’s ending ETH balance with the previously recorded withdrawn staking earnings in shares. Because the fee‑derived shares are included in that figure, the calculation subtracts the fee a second time, causing the user to receive less ETH than expected and leaving the excess fee amount trapped in the contract. The bug can be exploited by a user who deposits on the variable side, withdraws a portion of their balance while the vault is still active (isStarted() && !isEnded()), and then performs a second withdrawal after the vault has ended. In the first withdrawal the protocol fee is correctly deducted and recorded, but the fee’s share representation is also stored. During the final withdrawal the contract’s accounting treats those shares as part of the user’s earnings, effectively charging the fee twice. From the user’s perspective the UI shows a successful withdrawal request, but the received amount is lower than the amount they expected – for example a user who deposited 8 ETH may only receive 6 ETH. The protocol fee receiver also observes that a portion of the fee never arrives; the contract retains the unclaimed ETH, breaking the business logic that all fees should be transferred to the designated receiver. The issue appears only under the specific condition of variable‑side withdrawals before vault termination and is hard to notice because the contract’s external balance still reflects the total ETH held, while internal accounting mismatches are hidden in share‑based calculations. The vulnerability was discovered during a formal audit by reviewing the withdrawal logic and reproducing the scenario with a mock Lido implementation, which demonstrated the double‑fee effect and the stuck funds. To remediate the problem the fee‑derived shares must be excluded from the calculation of "stakesAmountOwed" (i.e., compute shares from the net amount after fee) and the total earnings formula at vault end must not subtract the already‑accounted protocol fee. By removing the fee from both the share conversion and the final earnings aggregation, the protocol fee is charged exactly once and the remaining earnings are correctly allocated to each variable user, restoring the intended accounting invariants and allowing the fee receiver to claim the full fee amount.
