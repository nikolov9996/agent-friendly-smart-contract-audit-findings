---
id: 22699
severity: "High"
---

# ITO can be manipulated

## Description

The ITO allocates 3 pZVE tokens per senior token minted and 1 pZVE token per junior token minted. When the offering period ends, users can claim the protocol ZVE token depending on the share of all pZVE they hold. Only 5% of the total ZVE tokens will be distributed to users, which is equal to 1.25M tokens. The ITO can be manipulated because it uses totalSupply() in its calculations. ZivoeITO.claimAirdrop() calculates the amount of ZVE tokens that should be vested to a certain user. It then creates a vesting schedule and sends all junior and senior tokens to their recipient. The formula is pZVEOwned=pZVETotal * totalZVEAirdropped (in the code these are called upper, middle and lower).
```solidity
uint256 upper = seniorCreditsOwned + juniorCreditsOwned;
uint256 middle = IERC20(IZivoeGlobals_ITO(GBL).ZVE()).totalSupply() / 20;
uint256 lower = IERC20(IZivoeGlobals_ITO(GBL).zSTT()).totalSupply() * 3 + (
    IERC20(IZivoeGlobals_ITO(GBL).zJTT()).totalSupply()
);
```
These calculations can be manipulated because they use totalSupply(). The tranche tokens have a public burn() function. An attacker can use 2 accounts to enter the ITO. They will deposit large amounts of stablecoins towards the senior tranche. When the airdrop starts, they can claim their senior tokens and start vesting ZVE tokens. The senior tokens can then be burned. Now, when the attacker calls the claimAirdrop function with their second account, the denominator of the above equation will be much smaller, allowing them to claim much more ZVE tokens than they are entitled to. There are 2 impacts from exploiting this vulnerability: • a malicious entity can claim excessively large part of the airdrop and gain governance power in the protocol • since the attacker would have gained unexpectedly large amount of ZVE tokens and the total ZVE to be distributed will be 1.25M, the users that claim after the attacker may not be able to do so if the amount they are entitled to, added to the stolen ZVE, exceeds 1.25M. Add this function to Test_ZivoeITO.sol and import the console. the logs.
```solidity
function test_StealZVE() public {
    // Sam is an honest actor, while Bob is a malicious one
    mint("DAI", address(sam), 3_000_000 ether);
    mint("DAI", address(bob), 2_000_000 ether);
    zvl.try_commence(address(ITO));
    // Bob has another Ethereum account, Sue
    bob.try_transferToken(DAI, address(sue), 1_000_000 ether);
    // give approvals
    assert(sam.try_approveToken(DAI, address(ITO), type(uint256).max));
    assert(bob.try_approveToken(DAI, address(ITO), type(uint256).max));
    assert(sue.try_approveToken(DAI, address(ITO), type(uint256).max));
    // Sam deposits 2M DAI to senior tranche and 400k to the junior one
    hevm.prank(address(sam));
    ITO.depositBoth(2_000_000 ether, DAI, 400_000, DAI);
    // Bob deposits 2M DAI into the senior tranche using his both accounts
    hevm.prank(address(bob));
    ITO.depositSenior(1_000_000 ether, DAI);
    hevm.prank(address(sue));
    ITO.depositSenior(1_000_000 ether, DAI);
    // Move the timestamp after the end of the ITO
    hevm.warp(block.timestamp + 31 days);
    ITO.claimAirdrop(address(sue));
    (, , , uint256 totalVesting, , , ) = vestZVE.viewSchedule(address(sue));
    // Sue burn all senior tokens
    vm.prank(address(sue));
    zSTT.burn(1_000_000 ether);
    console.log('Sue vesting: ', totalVesting / 1e18);
    ITO.claimAirdrop(address(bob));
    (, , , totalVesting, , , ) = vestZVE.viewSchedule(address(bob));
    console.log('Bob vesting: ', totalVesting / 1e18);
    ITO.claimAirdrop(address(sam));
    (, , , totalVesting, , , ) = vestZVE.viewSchedule(address(sam));
    console.log('Sam vesting: ', totalVesting / 1e18);
}
```
Fair vesting without prior burning Sue vesting: 312499 Bob vesting: 312499 Sam vesting: 625001 Vesting after burning Sue vesting: 312499 Bob vesting: Sam vesting: Bob and Sue will be able to claim ~750 000 ZVE tokens and Sam will not be able to claim any, because the total exceeds 1.25M.

## Proof of Concept

no poc

## Recommendation

Introduce a few new variables in the ITO contract.
```solidity
bool hasAirdropped;
uint256 totalZVE;
uint256 totalzSTT;
uint256 totalzJTT;
```
Then check if the call to claimAidrop is a first one and if it is, initialize the variables. Use these variables in the vesting calculations.
```solidity
function claimAirdrop(address depositor) external returns (
    uint256 zSTTClaimed, uint256 zJTTClaimed, uint256 ZVEVested
) {
    ...
    if (!hasAirdropped) {
        totalZVE = IERC20(IZivoeGlobals_ITO(GBL).ZVE()).totalSupply();
        totalzSTT = IERC20(IZivoeGlobals_ITO(GBL).zSTT()).totalSupply();
        totalzJTT = IERC20(IZivoeGlobals_ITO(GBL).zJTT()).totalSupply();
        hasAirdropped = true;
    }
    ...
    uint256 upper = seniorCreditsOwned + juniorCreditsOwned;
    uint256 middle = totalZVE / 20;
    uint256 lower = totalzSTT * 3 + totalzJTT;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the Initial Token Offering (ITO) airdrop calculation, which determines how many ZVE governance tokens each participant receives after the offering period ends. The contract computes each user’s share by multiplying the total amount of pseudo‑ZVE (pZVE) tokens they own (senior and junior credits) with a fraction of the total ZVE supply, where the denominator is derived from the current totalSupply() of the ZVE token and the totalSupply() of the senior (zSTT) and junior (zJTT) tranche tokens. Because totalSupply() is a mutable value that can be reduced by anyone calling the public burn() function on the tranche tokens, the denominator can be artificially shrunk after an initial claim. An attacker can therefore deposit a large amount of stablecoins into the senior tranche using two separate accounts, claim the airdrop for the first account, then burn the senior tokens held by the second account before invoking claimAirdrop for the second account. The reduced totalSupply() of the senior tranche makes the lower part of the formula smaller, inflating the calculated ZVE entitlement for the second account. This manipulation allows the attacker to claim a disproportionately large portion of the fixed 1.25 million ZVE tokens, potentially gaining excessive governance power and starving honest participants of their expected allocation. The issue occurs only when the tranche tokens expose a public burn function and the ITO contract relies on live totalSupply() values at claim time instead of a snapshot taken at the start of the airdrop. It was discovered during a manual audit that examined the arithmetic of claimAirdrop and noticed the use of totalSupply() without any protection against later changes. The bug is subtle because totalSupply() is commonly assumed to be a stable reference for token economics, and the burn operation is a legitimate feature that does not raise immediate red flags. From a user’s perspective, an honest participant may see their expected ZVE reward reduced to zero or a very small amount, while the attacker receives a large tranche of tokens, violating the protocol’s intended fair‑distribution logic. The root cause is the lack of a snapshot or immutable reference for the total token supplies used in the allocation formula. The recommended mitigation is to capture the total ZVE, total senior, and total junior supplies in immutable variables the first time any claim is made (or at the start of the airdrop) and use those snapshot values for all subsequent calculations, thereby preventing post‑claim supply manipulation.
