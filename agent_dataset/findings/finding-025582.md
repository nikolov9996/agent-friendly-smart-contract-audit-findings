---
id: 25582
severity: "Crit/High"
---

# The incorrect accounting of protocol fee will cause double charging fee and wrong distribution of earnings for variable users

## Description



## Proof of Concept

Add a setter in `LidoVault.sol` to set `lido` and `lidoWithdrawalQueue` to the mock version for easier debugging

[https://github.com/sherlock-audit/2024-08-saffron-finance/blob/38dd9c8436db341c331f1b14545770c1766fc0ee/lido-fiv/contracts/LidoVault.sol#L1003-L1007](<https://github.com/sherlock-audit/2024-08-saffron-finance/blob/38dd9c8436db341c331f1b14545770c1766fc0ee/lido-fiv/contracts/LidoVault.sol#L1003-L1007>)

```diff
  /// @notice Lido contract
- ILido public constant lido = ILido(0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84);
+ ILido public lido = ILido(0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84);

  /// @notice Lido withdrawal queue contract
- ILidoWithdrawalQueueERC721 public constant lidoWithdrawalQueue =
    ILidoWithdrawalQueueERC721(0x889edC2eDab5f40e902b864aD4d7AdE8E412F9B1);
+ ILidoWithdrawalQueueERC721 public lidoWithdrawalQueue =
    ILidoWithdrawalQueueERC721(0x889edC2eDab5f40e902b864aD4d7AdE8E412F9B1);

+ function setLidoInfo(address _lido, address _withdrawalQueue) public {
+   lido = ILido(_lido);
+   lidoWithdrawalQueue = ILidoWithdrawalQueueERC721(_withdrawalQueue);
+ }
```

Run command: `forge test --match-path test/PoC.t.sol -vv`

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

    address fixedDepositor = makeAddr('fixedDepositor');
    address alice = makeAddr('alice');
    address bob = makeAddr('bob');
    address feeReceiver = makeAddr('feeReceiver');

    uint256 protocolFeeBps = 2_000;
    uint256 fixedCap = 100 ether;
    uint256 variableCap = 10 ether;

    function setUp() public {
        lido = new MockLido();
        lidoWithdrawalQueueERC721 = new MockLidoWithdrawalQueueERC721(address(lido));

        factory = new VaultFactory(protocolFeeBps, 0);
        factory.setProtocolFeeReceiver(feeReceiver);

        factory.createVault(fixedCap, 1 days, variableCap);
        (,address addr) = factory.vaultInfo(1);
        vault = LidoVault(payable(addr));

        vault.setLidoInfo(address(lido), address(lidoWithdrawalQueueERC721));

        vm.deal(address(lidoWithdrawalQueueERC721), 1000 ether);

        vm.deal(fixedDepositor, fixedCap);

        vm.prank(fixedDepositor);
        vault.deposit{value: fixedCap}(0);
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

        vm.startPrank(fixedDepositor);
        vault.claimFixedPremium();
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

        vm.startPrank(fixedDepositor);
        vault.claimFixedPremium();
        vault.withdraw(0);
        vm.stopPrank();

        console.log("Vault's balance at the end: %e", address(vault).balance);
    }
}
```

```bash
testFirstVulnerabilityPath()
Logs:
  Alice's balance after first claim: 8e18
  Alice's balance at the end: 1.4e19
  Vault's balance at the end: 2e18
```

- Alice's final balance is only `8 ether + 6 ether = 14 ether`
- The `feeReceiver` and `fixedDepositor` have already withdrawn, but there is still ETH left in the contract.

```bash
testSecondVulnerabilityPath()
Logs:
  Alice's balance after first claim: 4e18
  Alice's balance at the end: 6.95e18
  Bob's balance at the end: 8.449999999999999999e18
  Vault's balance at the end: 1.000000000000000001e18
```

- Alice's final balance is only `4 ether + 2.95 ether = 6.95 ether`
- The `feeReceiver` and `fixedDepositor` have already withdrawn, but there is still ETH left in the contract.

## Impact

- The variable user, who withdraws when `isStarted()` and `!isEnded()`, will be charged more protocol fee when they withdraw when the vault ends
- The exceed protocol fee will be stuck in the contract
- Wrong distribution of the variable earnings

## Recommendation

`stakesAmountOwed` at `LidoVault.sol:534` should exclude the `protocolFee`

```diff
            uint256 protocolFee = ethAmountOwed.mulDiv(protocolFeeBps, 10000);
            totalProtocolFee += protocolFee;
-           uint256 stakesAmountOwed = lido.getSharesByPooledEth(ethAmountOwed);
+           uint256 stakesAmountOwed = lido.getSharesByPooledEth(ethAmountOwed - protocolFee );
```

`totalEarnings` at `LidoVault.sol:775` should exclude the deduction of `totalProtocolFee`

```diff
-     uint256 totalEarnings = vaultEndingETHBalance.mulDiv(withdrawnStakingEarningsInStakes,vaultEndingStakesAmount) - totalProtocolFee + vaultEndedStakingEarnings;
+     uint256 totalEarnings = vaultEndingETHBalance.mulDiv(withdrawnStakingEarningsInStakes,vaultEndingStakesAmount) + vaultEndedStakingEarnings;
```
